import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


PROJECTS_DIR = Path("projects")


def _now_text() -> str:
    """Return local machine time in a stable display/save format."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_filename(text: str) -> str:
    """
    Convert a project display name into a filesystem-safe filename stem.
    Internal project_id is still the authoritative identifier.
    """
    text = str(text or "").strip()
    if not text:
        return "mapping_project"

    text = re.sub(r'[<>:"/\\|?*]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120] or "mapping_project"


def ensure_projects_dir() -> Path:
    """Create the local projects directory if it does not exist."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECTS_DIR


def dataframe_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    """Serialize a DataFrame into JSON-safe record dictionaries."""
    if df is None or df.empty:
        return []

    safe_df = df.copy()

    # Normalize NaN/NaT to None so json.dump can serialize reliably.
    safe_df = safe_df.where(pd.notnull(safe_df), None)

    records = safe_df.to_dict(orient="records")

    # Final cleanup for pandas/numpy scalar-like values.
    cleaned = []
    for row in records:
        clean_row = {}
        for key, value in row.items():
            if hasattr(value, "item"):
                try:
                    value = value.item()
                except Exception:
                    pass

            if isinstance(value, (datetime,)):
                value = value.strftime("%Y-%m-%d %H:%M:%S")

            clean_row[str(key)] = value
        cleaned.append(clean_row)

    return cleaned


def records_to_dataframe(records: list[dict[str, Any]] | None) -> pd.DataFrame:
    """Restore a DataFrame from saved project record dictionaries."""
    return pd.DataFrame(records or [])


def create_project_metadata(
    project_name: str = "",
    source_file_name: str = "",
    target_file_name: str = "",
    source_file_hash: str = "",
    target_file_hash: str = "",
    source_structure_type: str = "",
    target_structure_type: str = "",
) -> dict[str, Any]:
    """
    Create metadata for a new Mapping Project.

    project_id is immutable and should not change when the project is renamed.
    """
    now = _now_text()

    return {
        "project_id": uuid.uuid4().hex,
        "project_name": str(project_name or "").strip(),
        "created_at": now,
        "last_saved_at": "",
        "source_file_name": source_file_name,
        "target_file_name": target_file_name,
        "source_file_hash": source_file_hash,
        "target_file_hash": target_file_hash,
        "source_structure_type": source_structure_type,
        "target_structure_type": target_structure_type,
    }


def build_default_project_name(interface_name: str = "") -> str:
    """
    Build the first-save default name.

    Project naming is intentionally independent from Interface Name.
    Example:
      InterfaceMapping_20261011_193522
    """
    return datetime.now().strftime("InterfaceMapping_%Y%m%d_%H%M%S")


def _project_path(project_id: str, project_name: str) -> Path:
    """
    Store by immutable ID so renaming does not create a different logical project.
    Name is included only for human readability.
    """
    ensure_projects_dir()

    safe_name = _safe_filename(project_name)
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(project_id or "")) or uuid.uuid4().hex

    return PROJECTS_DIR / f"{safe_name}__{safe_id}.json"


def _find_existing_project_path(project_id: str) -> Path | None:
    ensure_projects_dir()

    project_id = str(project_id or "").strip()
    if not project_id:
        return None

    matches = list(PROJECTS_DIR.glob(f"*__{project_id}.json"))
    if not matches:
        return None

    return matches[0]



def build_project_snapshot(
    *,
    metadata: dict[str, Any],
    interface_info_df: pd.DataFrame | None,
    source_transmission_df: pd.DataFrame | None,
    target_transmission_df: pd.DataFrame | None,
    mapping_df: pd.DataFrame | None,
    return_value_df: pd.DataFrame | None,
    reference_review_conflicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Build the authoritative persisted workspace snapshot.

    Phase 1 rule:
    - Do NOT store uploaded file binaries.
    - DO store every user-editable business value currently represented
      by the page DataFrames.
    - Also keep review/conflict state needed to reproduce the working view.

    Save Project should use this function only, so newly added editable
    page sections have one obvious place to be added in the future.
    """
    return {
        "schema_version": 1,
        "metadata": dict(metadata or {}),
        "workspace": {
            "interface_info_df": dataframe_to_records(interface_info_df),
            "source_transmission_df": dataframe_to_records(
                source_transmission_df
            ),
            "target_transmission_df": dataframe_to_records(
                target_transmission_df
            ),
            "mapping_df": dataframe_to_records(mapping_df),
            "return_value_df": dataframe_to_records(return_value_df),
            "reference_review_conflicts": list(
                reference_review_conflicts or []
            ),
        },
    }


def save_project(project_data: dict[str, Any]) -> dict[str, Any]:
    """
    Save or overwrite one project.

    Rename behavior:
    - project_id remains unchanged
    - if project_name changes, old filename is removed
    - a new readable filename is created
    """
    ensure_projects_dir()

    data = dict(project_data or {})
    metadata = dict(data.get("metadata") or {})

    project_id = str(metadata.get("project_id") or "").strip()
    if not project_id:
        project_id = uuid.uuid4().hex
        metadata["project_id"] = project_id

    project_name = str(metadata.get("project_name") or "").strip()
    if not project_name:
        project_name = build_default_project_name(
            metadata.get("interface_name", "")
        )
        metadata["project_name"] = project_name

    if not metadata.get("created_at"):
        metadata["created_at"] = _now_text()

    metadata["last_saved_at"] = _now_text()
    data["metadata"] = metadata

    old_path = _find_existing_project_path(project_id)
    new_path = _project_path(project_id, project_name)

    with new_path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    # If the project was renamed, remove the previous filename only after
    # the new file has been written successfully.
    if old_path is not None and old_path != new_path and old_path.exists():
        old_path.unlink()

    return {
        "project_id": project_id,
        "project_name": project_name,
        "last_saved_at": metadata["last_saved_at"],
        "path": str(new_path),
    }


def rename_project(project_id: str, new_project_name: str) -> dict[str, Any]:
    """
    Rename an existing project without changing its immutable project_id.
    """
    new_project_name = str(new_project_name or "").strip()
    if not new_project_name:
        raise ValueError("Project name cannot be empty.")

    data = load_project(project_id)
    metadata = dict(data.get("metadata") or {})
    metadata["project_name"] = new_project_name
    data["metadata"] = metadata

    return save_project(data)



def delete_project(project_id: str) -> None:
    """Delete one saved project by immutable project_id."""
    project_path = _find_existing_project_path(project_id)

    if project_path is None:
        raise FileNotFoundError(
            f"Saved project was not found: {project_id}"
        )

    project_path.unlink()


def load_project(project_id: str) -> dict[str, Any]:
    """Load a saved project by immutable project_id."""
    project_path = _find_existing_project_path(project_id)

    if project_path is None:
        raise FileNotFoundError(
            f"Saved project was not found: {project_id}"
        )

    with project_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("Saved project file has an invalid structure.")

    return data


def list_projects() -> list[dict[str, Any]]:
    """
    Return saved projects ordered by last saved time, newest first.

    Corrupted project files are skipped instead of breaking the entire UI.
    """
    ensure_projects_dir()

    projects = []

    for path in PROJECTS_DIR.glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            metadata = data.get("metadata") or {}

            project_id = str(metadata.get("project_id") or "").strip()
            if not project_id:
                continue

            projects.append(
                {
                    "project_id": project_id,
                    "project_name": str(
                        metadata.get("project_name") or path.stem
                    ),
                    "created_at": str(metadata.get("created_at") or ""),
                    "last_saved_at": str(metadata.get("last_saved_at") or ""),
                    "path": str(path),
                }
            )
        except Exception:
            # One bad project file must not stop other projects from loading.
            continue

    projects.sort(
        key=lambda item: item.get("last_saved_at", ""),
        reverse=True,
    )

    return projects
