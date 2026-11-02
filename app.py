import hashlib

import json

import os

import re

from datetime import date

from pathlib import Path as FilePath



import pandas as pd

import streamlit as st
import streamlit.components.v1 as components

from anthropic import Anthropic

from dotenv import load_dotenv

from pydantic import BaseModel



from exporters.excel_exporter import create_interface_mapping_excel

from mapping.mapping_service import build_mapping_rows

from parsers.excel_parser import parse_excel_reference
from parsers.json_parser import flatten_json

from parsers.soap_parser import (

    build_soap_ai_payload,

    read_soap_xml_file,

)

from services.document_ai_service import analyze_document_payload

from models.interface_package import InterfacePackage
from services.project_service import (
    build_default_project_name,
    build_project_snapshot,
    create_project_metadata,
    delete_project,
    list_projects,
    load_project,
    records_to_dataframe,
    rename_project,
    save_project,
)

from ui.mapping_grid import render_mapping_grid





# =========================

# Environment

# =========================

load_dotenv()



api_key = os.getenv("ANTHROPIC_API_KEY")

workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")

model_name = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")





# =========================

# Claude structured output

# =========================

class MappingItemAI(BaseModel):

    source_path: str

    source_field: str

    source_system: str

    source_pk: str

    source_type: str

    source_size: str

    source_description: str



    target_path: str

    target_field: str

    target_system: str

    target_pk: str

    target_type: str

    target_size: str

    target_description: str



    confidence: int

    reason: str





class ReturnValueAI(BaseModel):

    source_system: str

    source_table: str

    source_pk: str

    source_field: str

    source_type: str

    source_size: str

    source_description: str

    source_remark: str



    target_system: str

    target_table: str

    target_pk: str

    target_field: str

    target_type: str

    target_size: str

    target_description: str

    target_remark: str





class MappingAnalysisResult(BaseModel):

    mappings: list[MappingItemAI]

    return_values: list[ReturnValueAI]


class ExcelReferenceAIField(BaseModel):
    path: str = ""
    field: str = ""
    system: str = ""
    pk: str = ""
    type: str = ""
    size: str = ""
    description: str = ""
    sample: str = ""
    reference_sheet: str = ""
    reference_row: str = ""
    extraction_confidence: int = 60


class ExcelReferenceAIResult(BaseModel):
    fields: list[ExcelReferenceAIField]





# =========================

# File helpers

# =========================

def read_json_file(uploaded_file):

    raw = uploaded_file.getvalue().decode("utf-8-sig")

    return json.loads(raw)





def get_file_extension(uploaded_file):

    return FilePath(uploaded_file.name).suffix.lower()





STRUCTURE_FILE_TYPES = ["json", "xml"]

REFERENCE_FILE_TYPES = [
    "xlsx",
    "xls",
    "xlsm",
    "pdf",
    "docx",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "bmp",
    "tif",
    "tiff",
]


def get_structure_type(uploaded_file):
    """Return the supported Structure File type from its extension."""
    if uploaded_file is None:
        return ""

    extension = get_file_extension(uploaded_file)

    if extension == ".json":
        return "JSON"

    if extension == ".xml":
        return "XML"

    return ""


def normalize_standard_fields(fields):

    """

    Normalize fields from different parsers into the shared structure.



    Supports both:

    - Path / Field / Type / Sample

    - path / field / type / sample



    This keeps JSON and XML structure parsers compatible with

    the same shared field structure.

    """

    normalized = []



    for field in fields:

        if not isinstance(field, dict):

            continue



        field_name = str(

            field.get("Field")

            or field.get("field")

            or field.get("Name")

            or field.get("name")

            or ""

        ).strip()



        if not field_name:

            continue



        path = str(

            field.get("Path")

            or field.get("path")

            or ""

        ).strip()



        normalized_item = {

                "Path": path or field_name,

                "Field": field_name,

                "System": str(

                    field.get("System")

                    or field.get("system")

                    or ""

                ).strip(),

                "PK": str(

                    field.get("PK")

                    or field.get("pk")

                    or ""

                ).strip(),

                "Type": str(

                    field.get("Type")

                    or field.get("type")

                    or ""

                ).strip(),

                "Size": str(

                    field.get("Size")

                    or field.get("size")

                    or ""

                ).strip(),

                "Description": str(

                    field.get("Description")

                    or field.get("description")

                    or ""

                ).strip(),

                "Sample": str(

                    field.get("Sample")

                    or field.get("sample")

                    or ""

                ).strip(),

            }

        for extra_key in [
            "Required",
            "Level",
            "Seq",
            "Reference File",
            "Reference Sheet",
            "Reference Row",
            "Reference Table",
            "Sheet Category",
            "Message Section",
            "Field Origin",
            "Extraction Method",
            "Extraction Confidence",
            "Extraction Issues",
        ]:
            if extra_key in field:
                normalized_item[extra_key] = field.get(extra_key)

        normalized.append(normalized_item)



    return normalized





def analyze_uploaded_interface(
    uploaded_file,
    role,
):
    """
    Convert one Structure File into the shared field structure.

    Current 2.0 Structure File support:
    - JSON
    - XML

    Reference Documents are uploaded as part of the Interface Package,
    but are intentionally not analyzed in this step yet.
    """
    structure_type = get_structure_type(uploaded_file)

    if structure_type == "JSON":
        fields = flatten_json(
            read_json_file(uploaded_file)
        )

        return {
            "interface_id": "",
            "interface_name": "",
            "fields": normalize_standard_fields(fields),
        }

    if structure_type == "XML":
        parsed_xml = read_soap_xml_file(
            uploaded_file
        )

        payload = build_soap_ai_payload(
            parsed_xml
        )

        result = analyze_document_payload(
            document_payload=payload,
            role=role,
            file_name=uploaded_file.name,
            interface_context="GENERAL",
        )

        result["fields"] = normalize_standard_fields(
            result.get("fields", [])
        )

        return result

    raise ValueError(
        "Unsupported Structure File. "
        "Current 2.0 supports JSON and XML."
    )



def get_supported_excel_reference_files(reference_files):
    """Return currently analyzable Excel Reference Documents."""
    return [
        item
        for item in (reference_files or [])
        if get_file_extension(item) in [".xlsx", ".xlsm"]
    ]


def is_package_ready(package):
    """
    Supported modes:
    A. Structure + Reference
    B. Reference Only
    C. Structure Only
    """
    has_structure = (
        package.structure_file is not None
        and get_structure_type(package.structure_file)
        in ["JSON", "XML"]
    )

    has_excel_reference = bool(
        get_supported_excel_reference_files(
            package.reference_files
        )
    )

    return has_structure or has_excel_reference


def get_package_mode(package):
    has_structure = (
        package.structure_file is not None
        and get_structure_type(package.structure_file)
        in ["JSON", "XML"]
    )

    has_reference = bool(package.reference_files)

    if has_structure and has_reference:
        return "STRUCTURE_ENRICHED"

    if has_structure:
        return "STRUCTURE_ONLY"

    if has_reference:
        return "REFERENCE_ONLY"

    return "EMPTY"


def get_package_display_name(package):
    names = []

    if package.structure_file is not None:
        names.append(package.structure_file.name)

    names.extend(
        item.name
        for item in (package.reference_files or [])
    )

    return ", ".join(names)


def _clean_text(value):
    return "" if value is None else str(value).strip()


def _normalize_conflict_value(attribute, value):
    """Normalize comparable interface-definition values before conflict detection.

    Original values are preserved for display. This normalization is used
    only to determine whether Structure and Reference values are equivalent.
    """
    text = _clean_text(value)
    if not text:
        return ""

    attribute = _clean_text(attribute)

    if attribute == "Type":
        normalized = re.sub(r"\s+", "", text.lower())
        type_aliases = {
            "str": "string",
            "string": "string",
            "varchar": "string",
            "nvarchar": "string",
            "char": "string",
            "text": "string",
            "int": "integer",
            "integer": "integer",
            "long": "integer",
            "short": "integer",
            "bool": "boolean",
            "boolean": "boolean",
            "double": "number",
            "float": "number",
            "number": "number",
            "numeric": "number",
            "decimal": "decimal",
            "date": "date",
            "datetime": "datetime",
            "timestamp": "datetime",
            "object": "object",
            "array": "array",
            "list": "array",
        }
        return type_aliases.get(normalized, normalized)

    if attribute == "Size":
        normalized = text.replace(",", "").strip()
        try:
            number = float(normalized)
            if number.is_integer():
                return str(int(number))
            return str(number)
        except ValueError:
            return normalized.lower()

    if attribute == "PK":
        normalized = text.lower().strip()
        pk_aliases = {
            "y": "pk",
            "yes": "pk",
            "true": "pk",
            "1": "pk",
            "pk": "pk",
            "n": "",
            "no": "",
            "false": "",
            "0": "",
        }
        return pk_aliases.get(normalized, normalized)

    if attribute in {"Field", "System"}:
        return text.lower()

    if attribute == "Path":
        return re.sub(r"\s+", "", text)

    return text


def _normalized_field_key(field):
    path = _clean_text(field.get("Path", ""))

    if path:
        return ("PATH", path)

    return (
        "FIELD",
        _clean_text(
            field.get("Field", "")
        ).lower(),
    )


def merge_reference_fields(reference_field_groups):
    """
    Merge fields from multiple Reference Documents.

    Used mainly for Reference-only mode.
    Existing non-empty values are preserved;
    later documents only fill missing values.
    """
    merged = []
    key_to_index = {}

    for fields in reference_field_groups:
        for field in fields:
            key = _normalized_field_key(field)

            if not key[1]:
                continue

            if key not in key_to_index:
                key_to_index[key] = len(merged)
                merged.append(dict(field))
                continue

            existing = merged[key_to_index[key]]

            for column in [
                "Path",
                "Field",
                "System",
                "PK",
                "Type",
                "Size",
                "Description",
                "Sample",
                "Message Section",
                "Reference File",
                "Reference Sheet",
                "Reference Row",
                "Extraction Method",
                "Extraction Confidence",
            ]:
                if (
                    not _clean_text(
                        existing.get(column, "")
                    )
                    and _clean_text(
                        field.get(column, "")
                    )
                ):
                    existing[column] = field.get(
                        column,
                        "",
                    )

    return normalize_standard_fields(merged)


def enrich_structure_fields(
    structure_fields,
    reference_field_groups,
):
    """
    Enrich Structure fields with Reference evidence.

    Rule:
    JSON/XML is authoritative.

    Reference Documents:
    - may fill missing metadata;
    - may not create new Structure fields;
    - may not overwrite a non-empty Structure value.

    Conflicts are collected for later Review Required integration.
    """
    enriched = [
        dict(field)
        for field in structure_fields
    ]

    conflicts = []
    path_index = {}
    field_index = {}

    for index, field in enumerate(enriched):
        path = _clean_text(
            field.get("Path", "")
        )

        field_name = _clean_text(
            field.get("Field", "")
        ).lower()

        if path:
            path_index[path] = index

        if field_name:
            field_index.setdefault(
                field_name,
                [],
            ).append(index)

    for reference_fields in reference_field_groups:
        for reference in reference_fields:
            reference_path = _clean_text(
                reference.get("Path", "")
            )

            reference_field = _clean_text(
                reference.get("Field", "")
            ).lower()

            matched_index = None

            if (
                reference_path
                and reference_path in path_index
            ):
                matched_index = path_index[
                    reference_path
                ]

            elif reference_field:
                candidates = field_index.get(
                    reference_field,
                    [],
                )

                if len(candidates) == 1:
                    matched_index = candidates[0]

            # Reference must not create fields
            # that do not exist in Structure.
            if matched_index is None:
                continue

            structure = enriched[matched_index]

            for column in [
                "Path",
                "Field",
                "System",
                "PK",
                "Type",
                "Size",
                "Description",
                "Sample",
            ]:
                structure_value = _clean_text(
                    structure.get(column, "")
                )

                reference_value = _clean_text(
                    reference.get(column, "")
                )

                if (
                    not structure_value
                    and reference_value
                ):
                    structure[column] = reference_value
                    continue

                structure_compare_value = _normalize_conflict_value(
                    column,
                    structure_value,
                )
                reference_compare_value = _normalize_conflict_value(
                    column,
                    reference_value,
                )

                if (
                    structure_value
                    and reference_value
                    and structure_compare_value != reference_compare_value
                ):
                    conflicts.append(
                        {
                            "Path": structure.get(
                                "Path",
                                "",
                            ),
                            "Field": structure.get(
                                "Field",
                                "",
                            ),
                            "Attribute": column,
                            "Structure Value":
                                structure_value,
                            "Reference Value":
                                reference_value,
                        }
                    )

            # Provenance and request/response role are Reference evidence,
            # not competing Structure facts. Preserve them when available.
            for evidence_key in [
                "Message Section",
                "Reference File",
                "Reference Sheet",
                "Reference Row",
                "Extraction Method",
                "Extraction Confidence",
            ]:
                if (
                    not _clean_text(structure.get(evidence_key, ""))
                    and _clean_text(reference.get(evidence_key, ""))
                ):
                    structure[evidence_key] = reference.get(evidence_key)

    return (
        normalize_standard_fields(enriched),
        conflicts,
    )


REVIEW_WORTHY_REFERENCE_CONFLICT_ATTRIBUTES = {
    "Path",
    "Field",
    "System",
    "PK",
    "Type",
    "Size",
}


def apply_reference_conflicts_to_mapping_rows(
    mapping_rows,
    source_conflicts=None,
    target_conflicts=None,
):
    """
    Promote mapping rows to Review Required when Structure and Reference
    disagree on review-worthy interface-definition attributes.

    Structure remains authoritative. The conflict only changes review status
    and appends an audit-friendly explanation to AI Reason.
    """
    source_conflicts = source_conflicts or []
    target_conflicts = target_conflicts or []

    def build_indexes(side):
        path_key = f"{side}_path"
        field_key = f"{side}_field"
        path_index = {}
        field_index = {}

        for index, row in enumerate(mapping_rows):
            path = _clean_text(row.get(path_key, ""))
            field = _clean_text(row.get(field_key, "")).lower()

            if path:
                path_index.setdefault(path, []).append(index)
            if field:
                field_index.setdefault(field, []).append(index)

        return path_index, field_index

    def apply(conflicts, side, label):
        path_index, field_index = build_indexes(side)

        for conflict in conflicts:
            attribute = _clean_text(conflict.get("Attribute", ""))
            if attribute not in REVIEW_WORTHY_REFERENCE_CONFLICT_ATTRIBUTES:
                continue

            conflict_path = _clean_text(conflict.get("Path", ""))
            conflict_field = _clean_text(conflict.get("Field", "")).lower()

            indexes = []
            if conflict_path:
                indexes = path_index.get(conflict_path, [])

            if not indexes and conflict_field:
                candidates = field_index.get(conflict_field, [])
                if len(candidates) == 1:
                    indexes = candidates

            if not indexes:
                continue

            reason = (
                f"Reference Conflict ({label}) - {attribute}: "
                f"Structure='{_clean_text(conflict.get('Structure Value', ''))}' "
                f"vs Reference='{_clean_text(conflict.get('Reference Value', ''))}'. "
                "Structure value was kept."
            )

            for index in indexes:
                row = mapping_rows[index]
                row["mapping_status"] = "Review Required"

                existing_reason = _clean_text(row.get("ai_reason", ""))
                if reason not in existing_reason:
                    row["ai_reason"] = (
                        f"{existing_reason} | {reason}"
                        if existing_reason
                        else reason
                    )

    apply(source_conflicts, "source", "Source")
    apply(target_conflicts, "target", "Target")

    return mapping_rows


REVIEW_REASON_ORDER = [
    "Reference Conflict",
    "Low Confidence",
    "Transform Required",
    "Format Conversion",
]


def _normalize_mapping_type_name(value):
    text = _clean_text(value).lower()
    aliases = {
        "str": "string",
        "varchar": "string",
        "varchar2": "string",
        "char": "string",
        "text": "string",
        "int": "integer",
        "long": "integer",
        "short": "integer",
        "bool": "boolean",
        "float": "number",
        "double": "number",
        "decimal": "number",
        "numeric": "number",
    }
    return aliases.get(text, text)


def _safe_confidence(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _looks_like_format_conversion(reason):
    text = _clean_text(reason).lower()
    if not text:
        return False

    format_signals = [
        "format", "reformat", "date format", "datetime format",
        "timestamp format", "yyyy", "mm/dd", "dd/mm", "iso 8601",
    ]
    conversion_signals = [
        "convert", "conversion", "transform", "change",
        "different", "requires", "required",
    ]

    has_format = any(signal in text for signal in format_signals)
    has_conversion = any(signal in text for signal in conversion_signals)
    return has_format and has_conversion


def _looks_like_transform(row):
    source_type = _normalize_mapping_type_name(row.get("source_type", ""))
    target_type = _normalize_mapping_type_name(row.get("target_type", ""))

    # Different authoritative Structure types are a deterministic signal that
    # a conversion or explicit review may be needed. Empty types are ignored.
    if source_type and target_type and source_type != target_type:
        return True

    reason = _clean_text(row.get("ai_reason", "")).lower()
    transform_signals = [
        "transform", "convert", "conversion", "code mapping",
        "value mapping", "unit conversion", "requires mapping",
        "mapping rule",
    ]
    return any(signal in reason for signal in transform_signals)


def apply_review_reasons_to_mapping_rows(mapping_rows):
    """
    Derive user-facing Review Reason values without making another AI call.

    Review Required can be triggered by one or more of:
    - Reference Conflict: deterministic Structure/Reference disagreement.
    - Low Confidence: AI confidence below 75.
    - Transform Required: type mismatch or explicit transform language.
    - Format Conversion: explicit format conversion language.

    Multiple reasons are stored as a semicolon-separated display value.
    Source Only / Target Only remain their own statuses and do not receive a
    Review Reason.
    """
    for row in mapping_rows:
        status = _clean_text(row.get("mapping_status", ""))

        if status in {"Source Only", "Target Only"}:
            row["review_reason"] = ""
            continue

        reasons = []
        ai_reason = _clean_text(row.get("ai_reason", ""))

        if "Reference Conflict (" in ai_reason:
            reasons.append("Reference Conflict")

        confidence = _safe_confidence(row.get("confidence", ""))
        if confidence is not None and confidence < 75:
            reasons.append("Low Confidence")

        format_conversion = _looks_like_format_conversion(ai_reason)
        transform_required = _looks_like_transform(row)

        if transform_required:
            reasons.append("Transform Required")
        if format_conversion:
            reasons.append("Format Conversion")

        # De-duplicate while keeping the agreed UI order.
        reason_set = set(reasons)
        ordered = [
            reason
            for reason in REVIEW_REASON_ORDER
            if reason in reason_set
        ]

        row["review_reason"] = "; ".join(ordered)

        if ordered:
            row["mapping_status"] = "Review Required"
        elif status == "Review Required":
            # Backward-compatible fallback: if an old rule marked the row for
            # review but no explicit reason can be reconstructed, keep status.
            row["review_reason"] = "Review Required"

    return mapping_rows


def analyze_unresolved_excel_payload(payload, role, file_name):
    """
    AI fallback for Excel content that deterministic parsing could not resolve.

    Only unresolved blocks are sent to AI. Existing deterministic fields are
    never re-interpreted or overwritten here.
    """
    if not payload.get("blocks"):
        return []

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY is required for AI-assisted Excel fallback."
        )

    if not workspace_id:
        raise ValueError(
            "ANTHROPIC_WORKSPACE_ID is required for AI-assisted Excel fallback."
        )

    client = Anthropic(
        api_key=api_key,
        default_headers={
            "anthropic-workspace-id": workspace_id,
        },
    )

    prompt = f"""
You are assisting a fault-tolerant enterprise interface Excel parser.

ROLE OF THIS STEP:
- Interpret ONLY Excel blocks that the deterministic parser could not resolve.
- Do NOT re-interpret already parsed fields.
- Do NOT invent fields that are not supported by the Excel content.
- Extract interface field definitions only when the evidence is reasonably clear.
- If a value cannot be determined, return "".
- Be conservative.

DOCUMENT ROLE:
{role}

REFERENCE FILE:
{file_name}

UNRESOLVED EXCEL PAYLOAD:
{json.dumps(payload, ensure_ascii=False, indent=2)}

FIELD RULES:
- field: actual interface parameter / element / field name.
- path: explicit field path when present; otherwise reconstruct only when hierarchy
  is clearly supported. If uncertain, use the field name itself.
- type: explicit data type only.
- size: explicit length / precision only. Never infer size from sample values.
- description: preserve the business/technical explanation supported by the sheet.
- sample: explicit example value only.
- reference_sheet: exact sheet name from the unresolved block.
- reference_row: source row when it can be identified.
- extraction_confidence: 0-100 confidence in the extraction itself, not Mapping.

Return only fields supported by the unresolved Excel blocks.
"""

    response = client.messages.parse(
        model=model_name,
        max_tokens=8000,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        output_format=ExcelReferenceAIResult,
    )

    parsed = response.parsed_output
    if parsed is None:
        return []

    return [
        {
            "Path": item.path,
            "Field": item.field,
            "System": item.system,
            "PK": item.pk,
            "Type": item.type,
            "Size": item.size,
            "Description": item.description,
            "Sample": item.sample,
            "Reference File": file_name,
            "Reference Sheet": item.reference_sheet,
            "Reference Row": item.reference_row,
            "Extraction Method": "ai_assisted",
            "Extraction Confidence": item.extraction_confidence,
        }
        for item in parsed.fields
        if item.field
    ]


def analyze_excel_reference(uploaded_file, role):
    """
    Analyze one Excel Reference Document with a robust hybrid strategy.

    1. Deterministic parser handles recognizable sheets/tables first.
    2. Only unresolved blocks are sent to Claude for AI assistance.
    3. AI fallback failures become warnings and do not crash Mapping.
    """
    extension = get_file_extension(uploaded_file)

    if extension not in [".xlsx", ".xlsm"]:
        return {
            "status": "failed",
            "interface_id": "",
            "interface_name": "",
            "fields": [],
            "warnings": [
                "Current Excel Reference parsing supports .xlsx and .xlsm."
            ],
            "needs_ai": False,
            "parsed_sheets": [],
            "unresolved_blocks": [],
        }

    def ai_assist(payload):
        return analyze_unresolved_excel_payload(
            payload=payload,
            role=role,
            file_name=uploaded_file.name,
        )

    result = parse_excel_reference(
        uploaded_file,
        ai_assist=ai_assist,
    )

    result["fields"] = normalize_standard_fields(
        result.get("fields", [])
    )

    return result


def analyze_interface_package(package, role):
    """
    Analyze one Interface Package.

    Mode A:
        Structure + Excel Reference
        -> Structure is authoritative;
           Reference fills missing metadata.

    Mode B:
        Excel Reference Only
        -> Reference fields are used directly.

    Mode C:
        Structure Only
        -> Existing JSON/XML flow.
    """
    structure_result = None

    if package.structure_file is not None:
        structure_result = analyze_uploaded_interface(
            uploaded_file=package.structure_file,
            role=role,
        )

    reference_results = []

    for reference_file in (
        get_supported_excel_reference_files(
            package.reference_files
        )
    ):
        reference_results.append(
            analyze_excel_reference(
                reference_file,
                role=role,
            )
        )

    reference_field_groups = [
        item.get("fields", [])
        for item in reference_results
    ]

    # Mode A / C
    if structure_result is not None:
        fields = structure_result.get(
            "fields",
            [],
        )

        conflicts = []

        if reference_field_groups:
            fields, conflicts = (
                enrich_structure_fields(
                    structure_fields=fields,
                    reference_field_groups=(
                        reference_field_groups
                    ),
                )
            )

        return {
            "interface_id":
                structure_result.get(
                    "interface_id",
                    "",
                )
                or next(
                    (
                        item.get(
                            "interface_id",
                            "",
                        )
                        for item in reference_results
                        if item.get(
                            "interface_id",
                            "",
                        )
                    ),
                    "",
                ),
            "interface_name":
                structure_result.get(
                    "interface_name",
                    "",
                )
                or next(
                    (
                        item.get(
                            "interface_name",
                            "",
                        )
                        for item in reference_results
                        if item.get(
                            "interface_name",
                            "",
                        )
                    ),
                    "",
                ),
            "fields": fields,
            "reference_conflicts": conflicts,
            "reference_warnings": [
                warning
                for item in reference_results
                for warning in item.get("warnings", [])
            ],
            "package_mode": get_package_mode(
                package
            ),
        }

    # Mode B
    if reference_field_groups:
        return {
            "interface_id": next(
                (
                    item.get(
                        "interface_id",
                        "",
                    )
                    for item in reference_results
                    if item.get(
                        "interface_id",
                        "",
                    )
                ),
                "",
            ),
            "interface_name": next(
                (
                    item.get(
                        "interface_name",
                        "",
                    )
                    for item in reference_results
                    if item.get(
                        "interface_name",
                        "",
                    )
                ),
                "",
            ),
            "fields": merge_reference_fields(
                reference_field_groups
            ),
            "reference_conflicts": [],
            "reference_warnings": [
                warning
                for item in reference_results
                for warning in item.get("warnings", [])
            ],
            "package_mode": "REFERENCE_ONLY",
        }

    raise ValueError(
        "No analyzable file was found in "
        f"the {role} Interface Package. "
        "Current Structure support: JSON/XML. "
        "Current Reference parsing support: "
        "XLSX/XLSM."
    )


def split_fields_by_message_section(fields):
    """
    Split normalized fields without guessing.

    Explicit RESPONSE fields are routed to Return Value. REQUEST and UNKNOWN
    stay in Mapping Specification so unusual customer documents do not lose data.
    """
    mapping_fields = []
    response_fields = []

    for field in fields or []:
        section = _clean_text(field.get("Message Section", "")).upper()
        if section == "RESPONSE":
            response_fields.append(field)
        else:
            mapping_fields.append(field)

    return mapping_fields, response_fields


def build_mapping_context(
    structure_type,
    side,
    package_mode,
):
    """
    Give the Mapping model evidence context.
    """
    if package_mode == "REFERENCE_ONLY":
        return f"""
{side} PACKAGE CONTEXT:
- This side is built from Reference Documents only.
- No JSON/XML Structure File is available.
- Treat documented field definitions as usable mapping evidence.
- Be conservative about field existence, hierarchy, and datatype
  when they are not explicitly documented.
- Do not invent missing structure information.
"""

    authority_prompt = f"""
{side} PACKAGE AUTHORITY:
- A Structure File exists on this side.
- JSON/XML Structure facts are authoritative.
- Reference Documents may enrich business meaning and missing metadata.
- If Reference information conflicts with Structure information,
  Structure information takes precedence.
"""

    if structure_type == "XML":
        return authority_prompt + f"""
{side} STRUCTURE CONTEXT:
- This Structure File is XML.
- Use the full XML element Path and hierarchy when interpreting fields.
- Consider parent business objects when generic field names repeat.
- Do not invent namespaces or schema metadata that are not explicitly
  supported by the uploaded Structure File.
"""

    if structure_type == "JSON":
        return authority_prompt + f"""
{side} STRUCTURE CONTEXT:
- This Structure File is JSON.
- Use the full JSON Path and hierarchy when interpreting fields.
- Consider parent business objects when generic field names repeat.
- Do not invent metadata that is not supported by the uploaded Structure File.
"""

    return authority_prompt


# =========================

# Hierarchy helpers

# =========================

def build_hierarchy_from_path(path):

    """
    Convert an internal field Path into a readable parent hierarchy.

    Examples:
        goodsSerialRuleList.goodsSerialRule.serialRuleType
        -> goodsSerialRuleList > goodsSerialRule

        items[].product.code
        -> items[] > product

    A flat field path returns an empty hierarchy.
    """

    if path is None:
        return ""

    text = str(path).strip()

    if not text:
        return ""

    parts = [
        part.strip()
        for part in re.split(r"\s*(?:\.|/|>)\s*", text)
        if part.strip()
    ]

    if len(parts) <= 1:
        return ""

    return " > ".join(parts[:-1])


def add_hierarchy_to_mapping_rows(mapping_rows):

    """
    Add persistent Source/Target Hierarchy values to Mapping rows.

    Hierarchy is derived once from the internal Path, then becomes a normal
    editable page value. Excel export therefore uses the user's reviewed
    Hierarchy value instead of recalculating it later.
    """

    for row in mapping_rows:
        if not str(row.get("source_hierarchy", "") or "").strip():
            row["source_hierarchy"] = build_hierarchy_from_path(
                row.get("source_path", "")
            )

        if not str(row.get("target_hierarchy", "") or "").strip():
            row["target_hierarchy"] = build_hierarchy_from_path(
                row.get("target_path", "")
            )

    return mapping_rows


# =========================

# Front-end column definitions

# =========================

INTERFACE_INFO_COLUMNS = [

    "생성일 / Creation Date",

    "작성자 / Author",

    "인터페이스 ID / Interface ID",

    "인터페이스 명 / Interface Name",

    "인터페이스 패턴 / Interface Pattern",

    "스케줄 구동 / Schedule Driven",

    "실행 주기 / Execution Cycle",

    "최대 레코드(건) / Max Records",

    "평균 레코드(건) / Average Records",

    "분할 건수 / Split Count",

]



SOURCE_TRANSMISSION_COLUMNS = [

    "담당자 명 / Contact Name",

    "담당자 소속 / Department",

    "담당자 연락처 / Contact",

    "연계 기술 / Integration Technology",

    "Source Svr / Source Server",

    "DB / Database",

    "ADAPTER / Adapter",

    "조회 패턴 / Query Pattern",

]



TARGET_TRANSMISSION_COLUMNS = [

    "담당자 명 / Contact Name",

    "담당자 소속 / Department",

    "담당자 연락처 / Contact",

    "연계 기술 / Integration Technology",

    "Target Svr / Target Server",

    "DB / Database",

    "ADAPTER / Adapter",

    "처리 패턴 / Processing Pattern",

]



MAPPING_GRID_COLUMNS = [

    "source_path",

    "source_system",

    "source_seq",

    "source_table",

    "source_pk",

    "source_hierarchy",

    "source_field",

    "source_type",

    "source_size",

    "source_description",

    "source_remark",

    "mapping",

    "mapping_status",

    "review_reason",

    "target_path",

    "target_system",

    "target_table",

    "target_pk",

    "target_hierarchy",

    "target_field",

    "target_type",

    "target_size",

    "target_description",

    "target_remark",

    "confidence",

    "ai_reason",

]



RETURN_VALUE_COLUMNS = [

    "송신 시스템 / Source System",

    "순번 / Seq.",

    "송신 테이블 / Source Table",

    "송신 PK / Source PK",

    "송신 필드명 / Source Field",

    "송신 타입 / Source Type",

    "송신 사이즈 / Source Size",

    "송신 설명 / Source Description",

    "송신 비고 / Source Remark",

    "Mapping / Mapping",

    "수신 시스템 / Target System",

    "수신 테이블 / Target Table",

    "수신 PK / Target PK",

    "수신 필드명 / Target Field",

    "수신 타입 / Target Type",

    "수신 사이즈 / Target Size",

    "수신 설명 / Target Description",

    "수신 비고 / Target Remark",

]





# =========================

# English-only UI labels

# =========================

INTERFACE_INFO_UI_LABELS = {

    "생성일 / Creation Date": "Creation Date",

    "작성자 / Author": "Author",

    "인터페이스 ID / Interface ID": "Interface ID",

    "인터페이스 명 / Interface Name": "Interface Name",

    "인터페이스 패턴 / Interface Pattern": "Interface Pattern",

    "스케줄 구동 / Schedule Driven": "Schedule Driven",

    "실행 주기 / Execution Cycle": "Execution Cycle",

    "최대 레코드(건) / Max Records": "Max Records",

    "평균 레코드(건) / Average Records": "Average Records",

    "분할 건수 / Split Count": "Split Count",

}



SOURCE_TRANSMISSION_UI_LABELS = {

    "담당자 명 / Contact Name": "Contact Name",

    "담당자 소속 / Department": "Department",

    "담당자 연락처 / Contact": "Contact",

    "연계 기술 / Integration Technology": "Integration Technology",

    "Source Svr / Source Server": "Source Svr",

    "DB / Database": "DB",

    "ADAPTER / Adapter": "ADAPTER",

    "조회 패턴 / Query Pattern": "Query Pattern",

}



TARGET_TRANSMISSION_UI_LABELS = {

    "담당자 명 / Contact Name": "Contact Name",

    "담당자 소속 / Department": "Department",

    "담당자 연락처 / Contact": "Contact",

    "연계 기술 / Integration Technology": "Integration Technology",

    "Target Svr / Target Server": "Target Svr",

    "DB / Database": "DB",

    "ADAPTER / Adapter": "ADAPTER",

    "처리 패턴 / Processing Pattern": "Processing Pattern",

}



RETURN_VALUE_UI_LABELS = {

    "송신 시스템 / Source System": "Source System",

    "순번 / Seq.": "Seq.",

    "송신 테이블 / Source Table": "Source Table",

    "송신 PK / Source PK": "Source PK",

    "송신 필드명 / Source Field": "Source Field",

    "송신 타입 / Source Type": "Source Type",

    "송신 사이즈 / Source Size": "Source Size",

    "송신 설명 / Source Description": "Source Description",

    "송신 비고 / Source Remark": "Source Remark",

    "Mapping / Mapping": "Mapping",

    "수신 시스템 / Target System": "Target System",

    "수신 테이블 / Target Table": "Target Table",

    "수신 PK / Target PK": "Target PK",

    "수신 필드명 / Target Field": "Target Field",

    "수신 타입 / Target Type": "Target Type",

    "수신 사이즈 / Target Size": "Target Size",

    "수신 설명 / Target Description": "Target Description",

    "수신 비고 / Target Remark": "Target Remark",

}





def make_text_column_config(label_map):

    return {

        internal_name: st.column_config.TextColumn(display_name)

        for internal_name, display_name in label_map.items()

    }





# =========================

# DataFrame builders

# =========================

def one_row_df(columns, initial=None):

    row = {column: "" for column in columns}



    if initial:

        row.update(initial)



    return pd.DataFrame(

        [row],

        columns=columns,

    )





def build_interface_info_df():

    return one_row_df(

        INTERFACE_INFO_COLUMNS,

        {

            "생성일 / Creation Date":

                date.today().strftime("%Y.%m.%d")

        },

    )





def build_mapping_df(source_fields=None):

    rows = []



    if source_fields:

        for seq, field in enumerate(

            source_fields,

            start=1,

        ):

            rows.append(

                {

                    "source_path": field.get("Path", ""),

                    "source_system": field.get("System", ""),

                    "source_seq": seq,

                    "source_table": "",

                    "source_pk": field.get("PK", ""),

                    "source_hierarchy": build_hierarchy_from_path(
                        field.get("Path", "")
                    ),

                    "source_field": field.get("Field", ""),

                    "source_type": field.get("Type", ""),

                    "source_size": field.get("Size", ""),

                    "source_description": field.get(

                        "Description", ""

                    ),

                    "source_remark": "",

                    "mapping": "",

                    "mapping_status": "Pending",

                    "review_reason": "",

                    "target_path": "",

                    "target_system": "",

                    "target_table": "",

                    "target_pk": "",

                    "target_hierarchy": "",

                    "target_field": "",

                    "target_type": "",

                    "target_size": "",

                    "target_description": "",

                    "target_remark": "",

                    "confidence": "",

                    "ai_reason": "",

                }

            )



    if not rows:

        rows.append(

            {

                "source_path": "",

                "source_system": "",

                "source_seq": 1,

                "source_table": "",

                "source_pk": "",

                "source_hierarchy": "",

                "source_field": "",

                "source_type": "",

                "source_size": "",

                "source_description": "",

                "source_remark": "",

                "mapping": "",

                "mapping_status": "Pending",

                "review_reason": "",

                "target_path": "",

                "target_system": "",

                "target_table": "",

                "target_pk": "",

                "target_hierarchy": "",

                "target_field": "",

                "target_type": "",

                "target_size": "",

                "target_description": "",

                "target_remark": "",

                "confidence": "",

                "ai_reason": "",

            }

        )



    return pd.DataFrame(

        rows,

        columns=MAPPING_GRID_COLUMNS,

    )





def build_return_df():

    return one_row_df(

        RETURN_VALUE_COLUMNS,

        {

            "순번 / Seq.": 1,

            "Mapping / Mapping": "<-",

        },

    )





def reset_data(source_fields=None):

    st.session_state["interface_info_df"] = (

        build_interface_info_df()

    )



    st.session_state["source_transmission_df"] = (

        one_row_df(SOURCE_TRANSMISSION_COLUMNS)

    )



    st.session_state["target_transmission_df"] = (

        one_row_df(TARGET_TRANSMISSION_COLUMNS)

    )



    st.session_state["mapping_df"] = (

        build_mapping_df(source_fields)

    )



    st.session_state["return_value_df"] = (

        build_return_df()

    )

    # Clear conflict review data whenever uploaded package files change.
    st.session_state["reference_review_conflicts"] = []



    st.session_state["editor_version"] = (

        st.session_state.get(

            "editor_version",

            0,

        )

        + 1

    )





def merge_first_row(df, values):

    result = df.copy()



    for column, value in values.items():

        if (

            column in result.columns

            and value is not None

            and str(value).strip() != ""

        ):

            result.at[0, column] = value



    return result





# =========================

# Mapping enrichment helpers

# =========================

def enrich_source_fields(

    source_fields,

    ai_mappings,

):

    ai_by_path = {

        item.source_path: item

        for item in ai_mappings

        if item.source_path

    }



    result = []



    for field in source_fields:

        item = ai_by_path.get(

            field.get("Path", "")

        )



        result.append(

            {

                "Path": field.get("Path", ""),

                "Field": field.get("Field", ""),

                "System": (

                    item.source_system

                    if item and item.source_system

                    else field.get("System", "")

                ),

                "PK": (

                    item.source_pk

                    if item and item.source_pk

                    else field.get("PK", "")

                ),

                "Type": (

                    item.source_type

                    if item and item.source_type

                    else field.get("Type", "")

                ),

                "Size": (

                    item.source_size

                    if item and item.source_size

                    else field.get("Size", "")

                ),

                "Description": (

                    item.source_description

                    if item and item.source_description

                    else field.get("Description", "")

                ),

            }

        )



    return result





def enrich_target_fields(

    target_fields,

    ai_mappings,

):

    ai_by_path = {}



    for item in ai_mappings:

        if (

            item.target_path

            and item.target_path not in ai_by_path

        ):

            ai_by_path[item.target_path] = item



    result = []



    for field in target_fields:

        item = ai_by_path.get(

            field.get("Path", "")

        )



        result.append(

            {

                "Path": field.get("Path", ""),

                "Field": field.get("Field", ""),

                "System": (

                    item.target_system

                    if item and item.target_system

                    else field.get("System", "")

                ),

                "PK": (

                    item.target_pk

                    if item and item.target_pk

                    else field.get("PK", "")

                ),

                "Type": (

                    item.target_type

                    if item and item.target_type

                    else field.get("Type", "")

                ),

                "Size": (

                    item.target_size

                    if item and item.target_size

                    else field.get("Size", "")

                ),

                "Description": (

                    item.target_description

                    if item and item.target_description

                    else field.get("Description", "")

                ),

            }

        )



    return result





# =========================

# Excel export adapter

# =========================

def build_export_mapping_df(mapping_df):

    """

    Convert the new AgGrid Mapping data model into the formal

    bilingual column keys expected by excel_exporter.py.



    AI-only review fields such as confidence / AI reason / status

    are intentionally not exported into the company template.

    """

    rows = []



    if mapping_df is None or mapping_df.empty:

        return pd.DataFrame()



    for item in mapping_df.to_dict(orient="records"):

        rows.append(

            {

                "송신 시스템 / Source System": item.get("source_system", ""),

                "순번 / Seq.": (
                    item.get("source_seq", "")
                    if (
                        _clean_text(item.get("source_field", ""))
                        or _clean_text(item.get("source_path", ""))
                    )
                    else ""
                ),

                "송신 테이블 / Source Table": item.get("source_table", ""),

                "송신 PK / Source PK": item.get("source_pk", ""),

                "송신 계층 / Source Hierarchy": (
                    item.get("source_hierarchy", "")
                    or build_hierarchy_from_path(item.get("source_path", ""))
                ),

                "송신 필드명 / Source Field": item.get("source_field", ""),

                "송신 타입 / Source Type": item.get("source_type", ""),

                "송신 사이즈 / Source Size": item.get("source_size", ""),

                "송신 설명 / Source Description": item.get(

                    "source_description", ""

                ),

                "송신 비고 / Source Remark": item.get("source_remark", ""),

                "Mapping / Mapping": item.get("mapping", ""),

                "최종 대상 필드 / Final Target Field": item.get(

                    "target_field", ""

                ),

                "수신 시스템 / Target System": item.get("target_system", ""),

                "수신 테이블 / Target Table": item.get("target_table", ""),

                "수신 PK / Target PK": item.get("target_pk", ""),

                "수신 계층 / Target Hierarchy": (
                    item.get("target_hierarchy", "")
                    or build_hierarchy_from_path(item.get("target_path", ""))
                ),

                "수신 타입 / Target Type": item.get("target_type", ""),

                "수신 사이즈 / Target Size": item.get("target_size", ""),

                "수신 설명 / Target Description": item.get(

                    "target_description", ""

                ),

                "수신 비고 / Target Remark": item.get("target_remark", ""),

            }

        )



    return pd.DataFrame(rows)





# =========================

# Page

# =========================

st.set_page_config(

    page_title="Interface Mapping Assistant 2.0",

    page_icon="🔗",

    layout="wide",

)



st.title("🔗 Interface Mapping Assistant 2.0")

st.caption(

    "AI-powered interface field mapping assistant"

)





def _workspace_digest(
    *,
    interface_info_df=None,
    source_transmission_df=None,
    target_transmission_df=None,
    mapping_df=None,
    return_value_df=None,
    reference_review_conflicts=None,
):
    """
    Stable digest of the editable workspace only.
    Project metadata such as name / last_saved_at is intentionally excluded.
    """
    snapshot = build_project_snapshot(
        metadata={},
        interface_info_df=interface_info_df,
        source_transmission_df=source_transmission_df,
        target_transmission_df=target_transmission_df,
        mapping_df=mapping_df,
        return_value_df=return_value_df,
        reference_review_conflicts=reference_review_conflicts or [],
    )
    payload = json.dumps(
        snapshot.get("workspace", {}),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _current_workspace_digest():
    return _workspace_digest(
        interface_info_df=st.session_state.get("interface_info_df"),
        source_transmission_df=st.session_state.get(
            "source_transmission_df"
        ),
        target_transmission_df=st.session_state.get(
            "target_transmission_df"
        ),
        mapping_df=st.session_state.get("mapping_df"),
        return_value_df=st.session_state.get("return_value_df"),
        reference_review_conflicts=st.session_state.get(
            "reference_review_conflicts",
            [],
        ),
    )



def _workspace_has_meaningful_content():
    """
    Return True only when the current NEW workspace contains user work
    that should be protected/saved.

    Important:
    - Ignore auto-generated/default-only values.
    - Do not treat stale/generated Mapping metadata as user work when there
      is no actual Source/Target field content.
    """
    # Uploaded files mean the user has started a real Mapping workflow.
    for key in [
        "source_structure_file",
        "target_structure_file",
        "source_reference_files",
        "target_reference_files",
    ]:
        value = st.session_state.get(key)
        if value:
            return True

    # Mapping counts as meaningful only when at least one actual field exists.
    mapping_df = st.session_state.get("mapping_df")
    if isinstance(mapping_df, pd.DataFrame) and not mapping_df.empty:
        source_series = mapping_df.get(
            "source_field",
            pd.Series("", index=mapping_df.index),
        ).fillna("").astype(str).str.strip()

        target_series = mapping_df.get(
            "target_field",
            pd.Series("", index=mapping_df.index),
        ).fillna("").astype(str).str.strip()

        if source_series.ne("").any() or target_series.ne("").any():
            return True

    # Interface Information: Creation Date is auto-filled, so ignore it.
    interface_df = st.session_state.get("interface_info_df")
    if isinstance(interface_df, pd.DataFrame) and not interface_df.empty:
        for column in interface_df.columns:
            if column == "생성일 / Creation Date":
                continue

            values = (
                interface_df[column]
                .fillna("")
                .astype(str)
                .str.strip()
            )
            if values.ne("").any():
                return True

    # Transmission Information is fully user-editable.
    for key in [
        "source_transmission_df",
        "target_transmission_df",
    ]:
        df = st.session_state.get(key)

        if isinstance(df, pd.DataFrame) and not df.empty:
            normalized = (
                df.fillna("")
                .astype(str)
                .apply(lambda col: col.str.strip())
            )
            if normalized.ne("").any().any():
                return True

    # Return Value: ignore only its automatic defaults.
    return_df = st.session_state.get("return_value_df")
    if isinstance(return_df, pd.DataFrame) and not return_df.empty:
        check_df = return_df.copy()

        if "순번 / Seq." in check_df.columns:
            check_df["순번 / Seq."] = ""

        if "Mapping / Mapping" in check_df.columns:
            check_df["Mapping / Mapping"] = ""

        normalized = (
            check_df.fillna("")
            .astype(str)
            .apply(lambda col: col.str.strip())
        )
        if normalized.ne("").any().any():
            return True

    return False


def _workspace_has_unsaved_changes():
    """
    True when leaving the current workspace could discard user work.
    """
    current_project_id = str(
        st.session_state.get("current_project_id", "")
        or ""
    ).strip()

    if current_project_id:
        last_digest = str(
            st.session_state.get("last_saved_workspace_digest", "")
            or ""
        ).strip()

        if not last_digest:
            return True

        return _current_workspace_digest() != last_digest

    return _workspace_has_meaningful_content()



def _handle_registry_navigation_request():
    """Evaluate managed navigation after the editable workspace is updated."""
    if not st.session_state.get("app_nav_managed", False):
        return

    request = st.session_state.get("app_nav_registry_request")
    if request is None:
        return
    if request not in {"requested", "confirm"}:
        st.session_state.pop("app_nav_registry_request", None)
        return

    # Existing project operations take priority over a navigation request.
    if any(
        st.session_state.get(key)
        for key in (
            "pending_workspace_action",
            "project_save_requested",
            "unsaved_guard_visible",
            "pending_guard_action",
            "after_save_guard_action",
            "generate_mapping_requested",
            "project_rename_mode",
            "project_delete_mode",
            "project_new_mode",
            "project_load_confirm_mode",
            "pending_load_project_id",
            "load_after_save_project_id",
        )
    ):
        st.session_state.pop("app_nav_registry_request", None)
        with st.sidebar:
            st.info(
                "Navigation was cancelled because a project operation is pending. "
                "Complete that operation, then request navigation again."
            )
        return

    has_uploads = any(
        st.session_state.get(key)
        for key in (
            "source_structure_file",
            "target_structure_file",
            "source_reference_files",
            "target_reference_files",
        )
    )
    has_unsaved_changes = _workspace_has_unsaved_changes()

    # New mappings can contain manual edits without any field names yet.
    if not str(st.session_state.get("current_project_id") or "").strip():
        mapping_df = st.session_state.get("mapping_df")
        if isinstance(mapping_df, pd.DataFrame) and not mapping_df.empty:
            business_columns = [
                column
                for column in mapping_df.columns
                if column.startswith(("source_", "target_"))
                and column != "source_seq"
            ]
            business_values = (
                mapping_df[business_columns]
                .fillna("")
                .astype(str)
                .apply(lambda column: column.str.strip())
            )
            has_unsaved_changes = (
                has_unsaved_changes or business_values.ne("").any().any()
            )

    if not has_uploads and not has_unsaved_changes:
        st.session_state["app_nav_registry_request"] = "approved"
        return

    st.session_state["app_nav_registry_request"] = "confirm"
    with st.sidebar:
        confirmation = st.empty()
        with confirmation.container():
            st.warning(
                "Leaving AI Workspace does not save your changes. "
                "Unsaved edits may be lost. Uploaded files may not be "
                "restored when you return."
            )
            continue_navigation = st.button(
                "Continue to Registry",
                key="app_nav_confirm_registry",
                width="stretch",
            )
            cancel_navigation = st.button(
                "Cancel",
                key="app_nav_cancel_registry",
                width="stretch",
            )

        if cancel_navigation:
            st.session_state.pop("app_nav_registry_request", None)
            confirmation.empty()
        elif continue_navigation:
            st.session_state["app_nav_registry_request"] = "approved"
            confirmation.empty()


GUARD_ACTION_NEW_PROJECT = "NEW_PROJECT"
GUARD_ACTION_LOAD_PROJECT = "LOAD_PROJECT"
GUARD_ACTION_DELETE_PROJECT = "DELETE_PROJECT"
GUARD_ACTION_REGENERATE_MAPPING = "REGENERATE_MAPPING"


def _queue_workspace_action(action, payload=None):
    """
    Queue a workspace-changing action.

    The action is NOT evaluated here because Project controls are rendered
    before lower-page editors. The action is evaluated at the bottom of the
    page after all editable widgets have synchronized their latest values.
    """
    st.session_state.pop("app_nav_registry_request", None)
    st.session_state["pending_workspace_action"] = action
    st.session_state["pending_workspace_payload"] = dict(payload or {})


def _clear_pending_workspace_action():
    st.session_state["pending_workspace_action"] = ""
    st.session_state["pending_workspace_payload"] = {}


def _request_unsaved_guard(action, payload=None):
    """
    Queue one potentially destructive action.

    Any action that can replace, clear, regenerate, or permanently remove
    the current editable workspace should enter through this function.
    """
    st.session_state["pending_guard_action"] = action
    st.session_state["pending_guard_payload"] = dict(payload or {})
    st.session_state["unsaved_guard_visible"] = True


def _clear_unsaved_guard():
    st.session_state["pending_guard_action"] = ""
    st.session_state["pending_guard_payload"] = {}
    st.session_state["unsaved_guard_visible"] = False


def _guard_copy(action, payload=None):
    payload = payload or {}

    if action == GUARD_ACTION_NEW_PROJECT:
        return {
            "title": "Start a new project?",
            "message": (
                "You have unsaved changes. Starting a new project will clear "
                "the current workspace. Saved project data will not be deleted."
            ),
            "continue_label": "Start Without Saving",
            "save_label": "Save Current & Start New",
        }

    if action == GUARD_ACTION_LOAD_PROJECT:
        project_name = payload.get("project_name", "selected project")
        return {
            "title": "Load another project?",
            "message": (
                "You have unsaved changes in the current workspace. "
                f"Loading '{project_name}' will replace the current page."
            ),
            "continue_label": "Load Without Saving",
            "save_label": "Save Current & Load",
        }

    if action == GUARD_ACTION_DELETE_PROJECT:
        return {
            "title": "Delete current project?",
            "message": (
                "This project has unsaved changes. Deleting it will permanently "
                "remove the saved project and discard the current unsaved changes. "
                "This action cannot be undone."
            ),
            "continue_label": "Delete Without Saving",
            "save_label": "",
        }

    if action == GUARD_ACTION_REGENERATE_MAPPING:
        return {
            "title": "Regenerate Mapping?",
            "message": (
                "The current Mapping contains unsaved changes. Regenerating AI "
                "Mapping may replace your manual edits and review results."
            ),
            "continue_label": "Regenerate Without Saving",
            "save_label": "Save Current & Regenerate",
        }

    return {
        "title": "Continue?",
        "message": (
            "The current workspace contains unsaved changes that may be lost."
        ),
        "continue_label": "Continue Without Saving",
        "save_label": "Save Current & Continue",
    }


def _clear_active_workspace():
    """
    Clear the currently open work area.
    Saved Project files on disk are not affected.
    """
    st.session_state.pop("app_nav_registry_request", None)
    for widget_key in [
        "source_structure_file",
        "target_structure_file",
        "source_reference_files",
        "target_reference_files",
        "project_rename_input",
    ]:
        st.session_state.pop(widget_key, None)

    st.session_state["current_project_id"] = ""
    st.session_state["current_project_created_at"] = ""
    st.session_state["project_name"] = ""
    st.session_state["project_last_saved_at"] = ""
    st.session_state["last_saved_workspace_digest"] = ""
    st.session_state["reference_review_conflicts"] = []
    st.session_state["project_rename_mode"] = False
    st.session_state["project_delete_mode"] = False
    st.session_state["project_new_mode"] = False
    st.session_state["project_load_confirm_mode"] = False
    st.session_state["pending_load_project_id"] = ""
    st.session_state["load_after_save_project_id"] = ""
    _clear_unsaved_guard()
    st.session_state["after_save_guard_action"] = ""
    st.session_state["after_save_guard_payload"] = {}
    _clear_pending_workspace_action()

    reset_data(None)

    # With no uploaded files, the package signature later in this run is "|".
    # Set it now so the file-change guard does not wipe the freshly reset state
    # a second time.
    st.session_state["file_signature"] = "|"


def _restore_project_workspace(project_data):
    """
    Restore all persisted editable page values from one saved Project.
    Uploaded file binaries are intentionally not restored in Phase 1.
    """
    st.session_state.pop("app_nav_registry_request", None)
    metadata = dict(project_data.get("metadata") or {})
    workspace = dict(project_data.get("workspace") or {})

    st.session_state["interface_info_df"] = records_to_dataframe(
        workspace.get("interface_info_df")
    )
    st.session_state["source_transmission_df"] = records_to_dataframe(
        workspace.get("source_transmission_df")
    )
    st.session_state["target_transmission_df"] = records_to_dataframe(
        workspace.get("target_transmission_df")
    )
    st.session_state["mapping_df"] = records_to_dataframe(
        workspace.get("mapping_df")
    )
    st.session_state["return_value_df"] = records_to_dataframe(
        workspace.get("return_value_df")
    )
    st.session_state["reference_review_conflicts"] = list(
        workspace.get("reference_review_conflicts") or []
    )

    st.session_state["current_project_id"] = str(
        metadata.get("project_id") or ""
    )
    st.session_state["current_project_created_at"] = str(
        metadata.get("created_at") or ""
    )
    st.session_state["project_name"] = str(
        metadata.get("project_name") or ""
    )
    st.session_state["project_last_saved_at"] = str(
        metadata.get("last_saved_at") or ""
    )

    # Original uploaded files are not persisted, so clear upload widgets.
    for widget_key in [
        "source_structure_file",
        "target_structure_file",
        "source_reference_files",
        "target_reference_files",
    ]:
        st.session_state.pop(widget_key, None)

    st.session_state["file_signature"] = "|"
    st.session_state["editor_version"] = (
        st.session_state.get("editor_version", 0) + 1
    )

    st.session_state["project_rename_mode"] = False
    st.session_state["project_delete_mode"] = False
    st.session_state["project_new_mode"] = False
    st.session_state["project_load_confirm_mode"] = False
    st.session_state["pending_load_project_id"] = ""
    st.session_state["load_after_save_project_id"] = ""
    _clear_unsaved_guard()
    st.session_state["after_save_guard_action"] = ""
    st.session_state["after_save_guard_payload"] = {}
    _clear_pending_workspace_action()

    st.session_state["last_saved_workspace_digest"] = (
        _current_workspace_digest()
    )


# =========================
# Project workspace
# =========================
for state_key, default_value in {
    "current_project_id": "",
    "current_project_created_at": "",
    "project_name": "",
    "project_last_saved_at": "",
    "project_save_requested": False,
    "last_saved_workspace_digest": "",
    "project_rename_mode": False,
    "project_delete_mode": False,
    "project_new_mode": False,
    "project_load_confirm_mode": False,
    "pending_load_project_id": "",
    "load_after_save_project_id": "",
    "unsaved_guard_visible": False,
    "pending_guard_action": "",
    "pending_guard_payload": {},
    "after_save_guard_action": "",
    "after_save_guard_payload": {},
    "generate_mapping_requested": False,
    "pending_workspace_action": "",
    "pending_workspace_payload": {},
}.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value

# Deferred feedback appears after rerun, so it is not lost.
toast_message = st.session_state.pop("project_toast_message", "")
toast_icon = st.session_state.pop("project_toast_icon", None)
if toast_message:
    st.toast(toast_message, icon=toast_icon)

saved_projects = list_projects()
project_by_id = {
    project["project_id"]: project
    for project in saved_projects
}

# Some actions need to change the selectbox value. Do that only BEFORE
# the widget is instantiated to avoid Streamlit session_state errors.
if st.session_state.pop("clear_saved_project_selector", False):
    st.session_state["saved_project_selector"] = ""

forced_selector_id = st.session_state.pop(
    "force_project_selector_id",
    None,
)
if (
    forced_selector_id is not None
    and (
        forced_selector_id == ""
        or forced_selector_id in project_by_id
    )
):
    st.session_state["saved_project_selector"] = forced_selector_id

st.markdown("### **Project**")

with st.container(border=True):
    if saved_projects:
        current_project_id = str(
            st.session_state.get("current_project_id", "")
            or ""
        ).strip()

        saved_ids = [
            project["project_id"]
            for project in saved_projects
        ]

        # If a Current Project exists, keep a real saved project selected.
        # "Select a saved project" is reserved for New Project / empty workspace.
        if current_project_id and current_project_id in project_by_id:
            selector_options = saved_ids

            if (
                st.session_state.get("saved_project_selector")
                not in selector_options
            ):
                st.session_state["saved_project_selector"] = (
                    current_project_id
                )
        else:
            selector_options = [""] + saved_ids

        selected_project_id = st.selectbox(
            "Saved Projects",
            options=selector_options,
            format_func=lambda project_id: (
                "Select a saved project"
                if not project_id
                else project_by_id[project_id]["project_name"]
            ),
            key="saved_project_selector",
            help=(
                "Select a saved project here, then click Load Project. "
                "Selecting an item alone does not change the current workspace."
            ),
        )
    else:
        selected_project_id = ""
        st.selectbox(
            "Saved Projects",
            options=["No saved projects"],
            index=0,
            disabled=True,
            key="saved_project_selector_empty",
        )

    current_name = str(
        st.session_state.get("project_name") or ""
    ).strip()

    info_left, info_right = st.columns([1.25, 1])

    with info_left:
        st.markdown("**Current Project**")
        st.write(
            current_name
            if current_name
            else "New Project"
        )

    with info_right:
        st.markdown("**Last Saved**")
        st.write(
            st.session_state.get("project_last_saved_at")
            or "Not saved yet"
        )

    new_col, load_col, save_col, rename_col, delete_col = st.columns(5)

    with new_col:
        new_project_clicked = st.button(
            "New Project",
            use_container_width=True,
            help="Start a new empty Mapping workspace.",
        )

    load_enabled = bool(selected_project_id)

    with load_col:
        load_project_clicked = st.button(
            "Load Project",
            use_container_width=True,
            disabled=not load_enabled,
            help=(
                "Load the selected saved project into the current workspace."
                if load_enabled
                else None
            ),
        )

    with save_col:
        save_project_clicked = st.button(
            "Save Project",
            type="primary",
            use_container_width=True,
            help="Save the current Mapping workspace to a local project file.",
        )

    with rename_col:
        rename_mode_clicked = st.button(
            "Rename",
            use_container_width=True,
            disabled=not bool(
                st.session_state.get("current_project_id")
            ),
            help="Rename the current project.",
        )

    with delete_col:
        delete_mode_clicked = st.button(
            "Delete",
            use_container_width=True,
            disabled=not bool(
                st.session_state.get("current_project_id")
            ),
            help="Delete the current project.",
        )

    if new_project_clicked:
        st.session_state["project_rename_mode"] = False
        st.session_state["project_delete_mode"] = False
        _queue_workspace_action(
            GUARD_ACTION_NEW_PROJECT
        )
        st.rerun()

    if rename_mode_clicked:
        st.session_state["project_new_mode"] = False
        st.session_state["project_rename_mode"] = True
        st.session_state["project_delete_mode"] = False
        st.session_state["project_rename_input"] = current_name
        st.rerun()

    if delete_mode_clicked:
        st.session_state["project_new_mode"] = False
        st.session_state["project_rename_mode"] = False
        _queue_workspace_action(
            GUARD_ACTION_DELETE_PROJECT
        )
        st.rerun()

    if st.session_state.get("unsaved_guard_visible", False):
        guard_action = st.session_state.get(
            "pending_guard_action",
            "",
        )
        guard_payload = st.session_state.get(
            "pending_guard_payload",
            {},
        )
        guard_text = _guard_copy(
            guard_action,
            guard_payload,
        )

        st.divider()
        st.markdown(f"**{guard_text['title']}**")
        st.warning(guard_text["message"])

        has_save_option = bool(
            guard_text.get("save_label")
        )

        if has_save_option:
            guard_save_col, guard_continue_col, guard_cancel_col, _ = (
                st.columns([1.25, 1.25, 1, 1.2])
            )
        else:
            guard_continue_col, guard_cancel_col, _ = (
                st.columns([1.25, 1, 2.45])
            )
            guard_save_col = None

        save_then_continue = False
        if guard_save_col is not None:
            with guard_save_col:
                save_then_continue = st.button(
                    guard_text["save_label"],
                    type="primary",
                    use_container_width=True,
                    key="guard_save_then_continue",
                )

        with guard_continue_col:
            continue_without_saving = st.button(
                guard_text["continue_label"],
                use_container_width=True,
                key="guard_continue_without_saving",
            )

        with guard_cancel_col:
            cancel_guard = st.button(
                "Cancel",
                use_container_width=True,
                key="guard_cancel",
            )

        if cancel_guard:
            current_project_id = str(
                st.session_state.get(
                    "current_project_id",
                    "",
                )
                or ""
            )
            _clear_unsaved_guard()

            if current_project_id:
                st.session_state[
                    "force_project_selector_id"
                ] = current_project_id

            st.rerun()

        if save_then_continue:
            st.session_state["after_save_guard_action"] = (
                guard_action
            )
            st.session_state["after_save_guard_payload"] = dict(
                guard_payload or {}
            )
            _clear_unsaved_guard()
            st.session_state["project_save_requested"] = True

        if continue_without_saving:
            action = guard_action
            payload = dict(guard_payload or {})
            _clear_unsaved_guard()

            if action == GUARD_ACTION_NEW_PROJECT:
                _clear_active_workspace()
                st.session_state[
                    "clear_saved_project_selector"
                ] = True
                st.session_state[
                    "project_toast_message"
                ] = "New project workspace created."
                st.session_state[
                    "project_toast_icon"
                ] = "✅"
                st.rerun()

            elif action == GUARD_ACTION_LOAD_PROJECT:
                target_id = payload.get(
                    "project_id",
                    "",
                )
                try:
                    loaded_project = load_project(
                        target_id
                    )
                    _restore_project_workspace(
                        loaded_project
                    )
                    st.session_state[
                        "force_project_selector_id"
                    ] = target_id
                    st.session_state[
                        "project_toast_message"
                    ] = (
                        "Project loaded. Unsaved changes were discarded."
                    )
                    st.session_state[
                        "project_toast_icon"
                    ] = "⚠️"
                    st.rerun()
                except Exception as e:
                    st.error(
                        f"Failed to load project: {e}"
                    )

            elif action == GUARD_ACTION_DELETE_PROJECT:
                current_id = st.session_state.get(
                    "current_project_id",
                    "",
                )
                try:
                    delete_project(current_id)
                    _clear_active_workspace()
                    st.session_state[
                        "clear_saved_project_selector"
                    ] = True
                    st.session_state[
                        "project_toast_message"
                    ] = "Project deleted permanently."
                    st.session_state[
                        "project_toast_icon"
                    ] = "✅"
                    st.rerun()
                except Exception as e:
                    st.error(
                        f"Failed to delete project: {e}"
                    )

            elif action == GUARD_ACTION_REGENERATE_MAPPING:
                st.session_state[
                    "generate_mapping_requested"
                ] = True
                st.rerun()

    if st.session_state.get("project_rename_mode", False):
        st.divider()
        st.markdown("**Rename Project**")

        new_project_name = st.text_input(
            "New Project Name",
            key="project_rename_input",
        )

        rename_confirm_col, rename_cancel_col, _ = st.columns(
            [1, 1, 2]
        )

        with rename_confirm_col:
            confirm_rename = st.button(
                "Confirm Rename",
                type="primary",
                use_container_width=True,
            )

        with rename_cancel_col:
            cancel_rename = st.button(
                "Cancel",
                use_container_width=True,
            )

        if cancel_rename:
            st.session_state["project_rename_mode"] = False
            st.session_state.pop("project_rename_input", None)
            st.rerun()

        if confirm_rename:
            cleaned_name = str(new_project_name or "").strip()

            if not cleaned_name:
                st.warning("Project Name cannot be empty.")
            else:
                try:
                    rename_result = rename_project(
                        st.session_state["current_project_id"],
                        cleaned_name,
                    )

                    st.session_state["project_name"] = (
                        rename_result["project_name"]
                    )
                    st.session_state["project_last_saved_at"] = (
                        rename_result["last_saved_at"]
                    )
                    st.session_state["project_rename_mode"] = False
                    st.session_state.pop(
                        "project_rename_input",
                        None,
                    )
                    st.session_state[
                        "force_project_selector_id"
                    ] = rename_result["project_id"]
                    st.session_state["project_toast_message"] = (
                        "Project name updated successfully."
                    )
                    st.session_state["project_toast_icon"] = "✅"
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to rename project: {e}")

    if st.session_state.get("project_delete_mode", False):
        st.divider()
        st.warning(
            "Deleting this project will permanently remove the saved "
            "project and all saved modifications. This action cannot be undone. "
            "Please confirm only if you are sure you no longer need this project."
        )

        delete_confirm_col, delete_cancel_col, _ = st.columns(
            [1, 1, 2]
        )

        with delete_confirm_col:
            confirm_delete = st.button(
                "Delete Permanently",
                type="primary",
                use_container_width=True,
            )

        with delete_cancel_col:
            cancel_delete = st.button(
                "Cancel",
                use_container_width=True,
            )

        if cancel_delete:
            st.session_state["project_delete_mode"] = False
            st.rerun()

        if confirm_delete:
            current_id = st.session_state.get(
                "current_project_id",
                "",
            )
            try:
                delete_project(current_id)
                _clear_active_workspace()

                st.session_state[
                    "clear_saved_project_selector"
                ] = True
                st.session_state["project_toast_message"] = (
                    "Project deleted permanently."
                )
                st.session_state["project_toast_icon"] = "✅"
                st.rerun()
            except Exception as e:
                st.error(f"Failed to delete project: {e}")

if load_project_clicked:
    _queue_workspace_action(
        GUARD_ACTION_LOAD_PROJECT,
        {
            "project_id": selected_project_id,
            "project_name": (
                project_by_id.get(
                    selected_project_id,
                    {},
                ).get(
                    "project_name",
                    "selected project",
                )
            ),
        },
    )
    st.rerun()

if save_project_clicked:
    # Defer actual persistence until all editable widgets below have written
    # their newest values into session_state.
    st.session_state["project_save_requested"] = True


# =========================
# Compact Sticky Save Toolbar
# =========================
# Keep only the high-frequency Save action sticky. The full Project panel
# above continues to own New / Load / Rename / Delete.
st.markdown(
    """
    <style>
    .st-key-sticky_project_save_toolbar {
        position: sticky;
        top: 0.5rem;
        z-index: 999;
        padding: 0.35rem 0.65rem;
        margin: 0.35rem 0 0.65rem 0;
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 10px;
        background: var(--background-color, rgba(255, 255, 255, 0.96));
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08);
        backdrop-filter: blur(8px);
    }

    .st-key-sticky_project_save_toolbar [data-testid="stVerticalBlock"] {
        gap: 0.2rem;
    }

    .st-key-sticky_project_save_toolbar p {
        margin-bottom: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="sticky_project_save_toolbar"):
    sticky_name_col, sticky_saved_col, sticky_save_col = st.columns(
        [2.2, 1.6, 0.8],
        vertical_alignment="center",
    )

    sticky_project_name = str(
        st.session_state.get("project_name", "")
        or ""
    ).strip()

    with sticky_name_col:
        st.markdown(
            f"**Current Project:** "
            f"{sticky_project_name if sticky_project_name else 'New Project'}"
        )

    with sticky_saved_col:
        sticky_last_saved = str(
            st.session_state.get("project_last_saved_at", "")
            or ""
        ).strip()
        st.caption(
            f"Last Saved: {sticky_last_saved if sticky_last_saved else 'Not saved yet'}"
        )

    with sticky_save_col:
        sticky_save_clicked = st.button(
            "Save",
            type="primary",
            use_container_width=True,
            key="sticky_save_project",
            help="Save the current Mapping workspace. Shortcut: Ctrl+S / Cmd+S.",
        )

if sticky_save_clicked:
    # Do not save immediately. The existing Deferred Project Save at the
    # bottom of the page will run after all editors have synchronized.
    st.session_state["project_save_requested"] = True


# =========================
# Ctrl+S / Cmd+S shortcut
# =========================
# A keyboard shortcut should behave exactly like clicking the sticky Save
# button. First blur the active element so AG Grid commits an in-progress
# cell edit, then click the Save button.
components.html(
    """
    <script>
    (function () {
        const parentWindow = window.parent;
        const parentDocument = parentWindow.document;

        if (parentWindow.__interfaceMappingSaveShortcutInstalled) {
            return;
        }

        parentWindow.__interfaceMappingSaveShortcutInstalled = true;

        parentDocument.addEventListener(
            "keydown",
            function (event) {
                const isSaveShortcut =
                    (event.ctrlKey || event.metaKey) &&
                    String(event.key || "").toLowerCase() === "s";

                if (!isSaveShortcut) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                const active = parentDocument.activeElement;
                if (active && typeof active.blur === "function") {
                    active.blur();
                }

                // Give AG Grid a short moment to stop editing / commit the
                // active cell before triggering Streamlit Save.
                parentWindow.setTimeout(function () {
                    const buttons = Array.from(
                        parentDocument.querySelectorAll("button")
                    );

                    const saveButton = buttons.find(function (button) {
                        return (
                            !button.disabled &&
                            String(button.innerText || "").trim() === "Save"
                        );
                    });

                    if (saveButton) {
                        saveButton.click();
                    }
                }, 120);
            },
            true
        );
    })();
    </script>
    """,
    height=0,
    width=0,
)


STRUCTURE_FORMAT_HINT = (
    "JSON (.json) · XML (.xml)"
)

REFERENCE_FORMAT_HINT = (
    "Excel (.xlsx, .xls, .xlsm) · PDF (.pdf) · Word (.docx) · "
    "Images (.png, .jpg, .jpeg, .webp, .bmp, .tif, .tiff)"
)


# =========================
# Interface Package upload area
# =========================
left, right = st.columns(2)

with left:
    st.subheader("Source Interface Package")

    source_structure_file = st.file_uploader(
        "Structure File",
        type=STRUCTURE_FILE_TYPES,
        key="source_structure_file",
        help=(
            "Upload the Source interface structure. "
            "Current 2.0 supports JSON and XML."
        ),
    )

    st.caption(
        f"📐 Structure formats: {STRUCTURE_FORMAT_HINT}"
    )

    source_reference_files = st.file_uploader(
        "Reference Documents",
        type=REFERENCE_FILE_TYPES,
        accept_multiple_files=True,
        key="source_reference_files",
        help=(
            "Upload one or more documents that explain field meaning. "
            "Excel (.xlsx/.xlsm) is analyzed now; "
            "PDF, Word, and images will be connected later."
        ),
    )

    st.caption(
        f"📎 Reference formats: {REFERENCE_FORMAT_HINT}"
    )

with right:
    st.subheader("Target Interface Package")

    target_structure_file = st.file_uploader(
        "Structure File",
        type=STRUCTURE_FILE_TYPES,
        key="target_structure_file",
        help=(
            "Upload the Target interface structure. "
            "Current 2.0 supports JSON and XML."
        ),
    )

    st.caption(
        f"📐 Structure formats: {STRUCTURE_FORMAT_HINT}"
    )

    target_reference_files = st.file_uploader(
        "Reference Documents",
        type=REFERENCE_FILE_TYPES,
        accept_multiple_files=True,
        key="target_reference_files",
        help=(
            "Upload one or more documents that explain field meaning. "
            "Excel (.xlsx/.xlsm) is analyzed now; "
            "PDF, Word, and images will be connected later."
        ),
    )

    st.caption(
        f"📎 Reference formats: {REFERENCE_FORMAT_HINT}"
    )


source_package = InterfacePackage(
    structure_file=source_structure_file,
    reference_files=source_reference_files or [],
    role="source",
)

target_package = InterfacePackage(
    structure_file=target_structure_file,
    reference_files=target_reference_files or [],
    role="target",
)

source_structure_type = get_structure_type(
    source_package.structure_file
)

target_structure_type = get_structure_type(
    target_package.structure_file
)


unsupported_source_references = [
    reference.name
    for reference in source_package.reference_files
    if get_file_extension(reference)
    not in [".xlsx", ".xlsm"]
]

unsupported_target_references = [
    reference.name
    for reference in target_package.reference_files
    if get_file_extension(reference)
    not in [".xlsx", ".xlsm"]
]

if unsupported_source_references:
    st.caption(
        "ℹ️ Source Reference Documents uploaded but not analyzed yet: "
        + ", ".join(
            unsupported_source_references
        )
    )

if unsupported_target_references:
    st.caption(
        "ℹ️ Target Reference Documents uploaded but not analyzed yet: "
        + ", ".join(
            unsupported_target_references
        )
    )


# =========================
# Structure preview / validation
# =========================
source_preview_fields = None
target_preview_fields = None

if source_package.structure_file is not None:
    if source_structure_type == "JSON":
        try:
            source_preview_fields = normalize_standard_fields(
                flatten_json(
                    read_json_file(
                        source_package.structure_file
                    )
                )
            )
        except Exception as e:
            st.error(
                f"Failed to read Source JSON: {e}"
            )

    elif source_structure_type == "XML":
        st.info(
            "Source XML Structure File is ready. "
            "It will be parsed when AI Mapping is generated."
        )

if target_package.structure_file is not None:
    if target_structure_type == "JSON":
        try:
            target_preview_fields = normalize_standard_fields(
                flatten_json(
                    read_json_file(
                        target_package.structure_file
                    )
                )
            )
        except Exception as e:
            st.error(
                f"Failed to read Target JSON: {e}"
            )

    elif target_structure_type == "XML":
        st.info(
            "Target XML Structure File is ready. "
            "It will be parsed when AI Mapping is generated."
        )


# =========================
# Clear stale results when package files change
# =========================
signature_parts = [
    source_structure_type,
    target_structure_type,
]

for uploaded in [
    source_package.structure_file,
    target_package.structure_file,
    *source_package.reference_files,
    *target_package.reference_files,
]:
    if uploaded is not None:
        signature_parts.extend(
            [
                uploaded.name,
                hashlib.sha256(
                    uploaded.getvalue()
                ).hexdigest(),
            ]
        )

signature = "|".join(signature_parts)

if (
    st.session_state.get("file_signature")
    != signature
):
    st.session_state["file_signature"] = signature
    reset_data(source_preview_fields)

if "interface_info_df" not in st.session_state:
    reset_data(source_preview_fields)


# =========================
# AI Analysis readiness
# =========================
source_ready = is_package_ready(
    source_package
)

target_ready = is_package_ready(
    target_package
)


if (
    get_package_mode(source_package)
    == "REFERENCE_ONLY"
    and not source_ready
):
    st.info(
        "Source is Reference Documents Only. "
        "Current executable support requires "
        "at least one .xlsx or .xlsm file."
    )

if (
    get_package_mode(target_package)
    == "REFERENCE_ONLY"
    and not target_ready
):
    st.info(
        "Target is Reference Documents Only. "
        "Current executable support requires "
        "at least one .xlsx or .xlsm file."
    )


# =========================

# AI Analysis

# =========================

if source_ready and target_ready:

    st.divider()



    generate_mapping_clicked = st.button(

        "Generate AI Analysis & Mapping",

        type="primary",

    )

    if generate_mapping_clicked:
        _queue_workspace_action(
            GUARD_ACTION_REGENERATE_MAPPING
        )
        st.rerun()

    if st.session_state.pop(
        "generate_mapping_requested",
        False,
    ):

        if not api_key:

            st.error(

                "ANTHROPIC_API_KEY was not found."

            )

            st.stop()



        if not workspace_id:

            st.error(

                "ANTHROPIC_WORKSPACE_ID was not found."

            )

            st.stop()



        # =========================

        # Step 1: Parse / Analyze Source + Target

        # =========================

        try:

            with st.spinner(

                "Preparing Source interface..."

            ):

                source_result = analyze_interface_package(

                    package=source_package,

                    role="source",

                )



            with st.spinner(

                "Preparing Target interface..."

            ):

                target_result = analyze_interface_package(

                    package=target_package,

                    role="target",

                )



        except Exception as e:

            st.error(

                f"Interface parsing failed: {e}"

            )

            st.stop()



        all_source_fields = source_result["fields"]

        all_target_fields = target_result["fields"]

        source_fields, source_response_fields = split_fields_by_message_section(
            all_source_fields
        )
        target_fields, target_response_fields = split_fields_by_message_section(
            all_target_fields
        )

        source_reference_conflicts = source_result.get(
            "reference_conflicts",
            [],
        )
        target_reference_conflicts = target_result.get(
            "reference_conflicts",
            [],
        )

        for warning in source_result.get("reference_warnings", []):
            st.warning(f"Source Reference: {warning}")

        for warning in target_result.get("reference_warnings", []):
            st.warning(f"Target Reference: {warning}")

        review_conflicts = [
            ("Source", conflict)
            for conflict in source_reference_conflicts
            if conflict.get("Attribute")
            in REVIEW_WORTHY_REFERENCE_CONFLICT_ATTRIBUTES
        ] + [
            ("Target", conflict)
            for conflict in target_reference_conflicts
            if conflict.get("Attribute")
            in REVIEW_WORTHY_REFERENCE_CONFLICT_ATTRIBUTES
        ]

        # Persist review-worthy conflicts across st.rerun().
        # The stable UI is rendered later above Mapping Specification.
        st.session_state["reference_review_conflicts"] = [
            {
                "Side": side,
                "Path": conflict.get("Path", ""),
                "Field": conflict.get("Field", ""),
                "Attribute": conflict.get("Attribute", ""),
                "Structure Value": conflict.get("Structure Value", ""),
                "Reference Value": conflict.get("Reference Value", ""),
            }
            for side, conflict in review_conflicts
        ]



        if not source_fields:

            st.error(

                "No Source fields were extracted."

            )

            st.stop()



        if not target_fields:

            st.error(

                "No Target fields were extracted."

            )

            st.stop()



        # =========================

        # Populate Interface ID / Name when available

        # =========================

        source_interface_id = (

            source_result.get(

                "interface_id",

                "",

            )

        )



        source_interface_name = (

            source_result.get(

                "interface_name",

                "",

            )

        )



        target_interface_id = (

            target_result.get(

                "interface_id",

                "",

            )

        )



        target_interface_name = (

            target_result.get(

                "interface_name",

                "",

            )

        )



        detected_interface_id = (

            source_interface_id

            or target_interface_id

        )



        detected_interface_name = (

            source_interface_name

            or target_interface_name

        )



        st.session_state[

            "interface_info_df"

        ] = merge_first_row(

            st.session_state[

                "interface_info_df"

            ],

            {

                "인터페이스 ID / Interface ID":

                    detected_interface_id,

                "인터페이스 명 / Interface Name":

                    detected_interface_name,

            },

        )



        # =========================

        # Step 2: AI Mapping - chunked

        # Keep each Claude response compact to reduce the risk of
        # structured JSON being truncated.
        MAPPING_BATCH_SIZE = 15

        client = Anthropic(

            api_key=api_key,

            default_headers={

                "anthropic-workspace-id":

                    workspace_id

            },

        )



        source_mapping_context = build_mapping_context(

            source_structure_type,

            "SOURCE",

            source_result.get(
                "package_mode",
                get_package_mode(
                    source_package
                ),
            ),

        )



        target_mapping_context = build_mapping_context(

            target_structure_type,

            "TARGET",

            target_result.get(
                "package_mode",
                get_package_mode(
                    target_package
                ),
            ),

        )



        def call_mapping_batch(

            source_batch,

            batch_no,

            total_batches,

        ):

            batch_prompt = f"""

You are an enterprise interface mapping specialist.



This is mapping batch {batch_no} of {total_batches}.



Analyze ONLY:

1. Mapping Specification for the Source fields in THIS batch.



IMPORTANT GENERAL RULES:

- Never invent unsupported information.

- Unknown information must be returned as "".

- Do not force a mapping.

- Analyze every Source field in THIS batch.

- Always use full Path + Field together.

- Duplicate Field names may exist under different Paths.

- If no reliable Target exists, return target_path="" and target_field="".

- return_values MUST be [] in this batch.



SOURCE FILE:

{get_package_display_name(source_package)}



SOURCE STRUCTURE TYPE:

{source_structure_type}



TARGET FILE:

{get_package_display_name(target_package)}



TARGET STRUCTURE TYPE:

{target_structure_type}



{source_mapping_context}



{target_mapping_context}



SOURCE FIELDS FOR THIS BATCH:

{json.dumps(

    source_batch,

    ensure_ascii=False,

    indent=2,

)}



TARGET FIELDS:

{json.dumps(

    target_fields,

    ensure_ascii=False,

    indent=2,

)}



MAPPING RULES:

- source_path must exactly match an existing Source Path in THIS batch.

- source_field must match the Field belonging to source_path.

- Return one mapping item for every Source field in THIS batch.

- target_path must exactly match an existing Target Path,

  or be "" when no reliable match exists.

- target_field must match the Field belonging to target_path,

  or be "" when no reliable match exists.

- Prefer documented descriptions, types, sizes and system context

  when deciding mappings.

- Similar field names alone are not enough when business meaning differs.



FIELD EXTRACTION RULES:

- source_system / target_system:

  preserve or extract only when supported by the input.

  Otherwise "".

- source_pk / target_pk:

  return "PK" only when supported by the input.

  Otherwise "".

- source_type / target_type:

  preserve documented or parsed type information.

- source_size / target_size:

  preserve documented size information.

  Do not infer maximum size from a sample value.

- source_description / target_description:

  preserve supported descriptions.

  Otherwise "".

- Table is a manual-entry field and must not be inferred by AI.

- Remark is a manual-entry field and must not be inferred by AI.

- confidence must be 0-100.

- reason must briefly explain the mapping judgment.



OUTPUT REQUIREMENT:

- mappings: mapping items for THIS batch only.

- return_values: [].

"""

            last_error = None



            for attempt in range(2):

                try:

                    response = client.messages.parse(

                        model=model_name,

                        max_tokens=8000,

                        messages=[

                            {

                                "role": "user",

                                "content": batch_prompt,

                            }

                        ],

                        output_format=MappingAnalysisResult,

                    )



                    return response.parsed_output



                except Exception as e:

                    last_error = e



            raise RuntimeError(

                f"Mapping batch {batch_no}/{total_batches} "

                f"failed after retry: {last_error}"

            )



        def call_return_value_analysis():

            return_prompt = f"""

You are an enterprise interface mapping specialist.



Analyze ONLY:

Return Value / response fields.



IMPORTANT RULES:

- Never invent unsupported information.

- Unknown information must be returned as "".

- Use only the explicit RESPONSE fields supplied below.
- If either side has no explicit response fields, do not invent them.
- If no reliable response mapping exists, return return_values=[].

- mappings MUST be [].

- Table and Remark are manual-entry fields and must not be invented.



SOURCE FILE:

{get_package_display_name(source_package)}



SOURCE STRUCTURE TYPE:

{source_structure_type}



TARGET FILE:

{get_package_display_name(target_package)}



TARGET STRUCTURE TYPE:

{target_structure_type}



{source_mapping_context}



{target_mapping_context}



SOURCE RESPONSE FIELDS:

{json.dumps(

    source_response_fields,

    ensure_ascii=False,

    indent=2,

)}



TARGET RESPONSE FIELDS:

{json.dumps(

    target_response_fields,

    ensure_ascii=False,

    indent=2,

)}



OUTPUT REQUIREMENT:

- mappings: [].

- return_values: only explicitly supported return/response fields.

"""

            last_error = None



            for attempt in range(2):

                try:

                    response = client.messages.parse(

                        model=model_name,

                        max_tokens=6000,

                        messages=[

                            {

                                "role": "user",

                                "content": return_prompt,

                            }

                        ],

                        output_format=MappingAnalysisResult,

                    )



                    return response.parsed_output



                except Exception as e:

                    last_error = e



            raise RuntimeError(

                "Return Value analysis failed after retry: "

                f"{last_error}"

            )



        with st.spinner(

            "Claude is mapping Source and Target fields in batches..."

        ):

            try:

                source_batches = [

                    source_fields[i:i + MAPPING_BATCH_SIZE]

                    for i in range(

                        0,

                        len(source_fields),

                        MAPPING_BATCH_SIZE,

                    )

                ]



                all_mappings = []



                for batch_index, source_batch in enumerate(

                    source_batches,

                    start=1,

                ):

                    batch_result = call_mapping_batch(

                        source_batch=source_batch,

                        batch_no=batch_index,

                        total_batches=len(source_batches),

                    )



                    all_mappings.extend(

                        batch_result.mappings

                    )



                return_result = call_return_value_analysis()



                ai = MappingAnalysisResult(

                    mappings=all_mappings,

                    return_values=return_result.return_values,

                )



            except Exception as e:

                st.error(

                    f"Claude Mapping API call failed: {e}"

                )

                st.stop()



        # =========================

        # 3. Mapping Specification

        # =========================

        enriched_source_fields = (

            enrich_source_fields(

                source_fields,

                ai.mappings,

            )

        )



        enriched_target_fields = (

            enrich_target_fields(

                target_fields,

                ai.mappings,

            )

        )



        ai_mapping_dicts = [

            item.model_dump()

            for item in ai.mappings

        ]



        mapping_rows = build_mapping_rows(

            enriched_source_fields,

            enriched_target_fields,

            ai_mapping_dicts,

        )

        mapping_rows = add_hierarchy_to_mapping_rows(
            mapping_rows
        )

        mapping_rows = apply_reference_conflicts_to_mapping_rows(
            mapping_rows=mapping_rows,
            source_conflicts=source_reference_conflicts,
            target_conflicts=target_reference_conflicts,
        )

        mapping_rows = apply_review_reasons_to_mapping_rows(
            mapping_rows
        )

        # Target-only rows do not correspond to a Source field.
        # Therefore Source Seq. must stay blank instead of continuing 50, 51, ...
        for row in mapping_rows:
            if row.get("mapping_status") == "Target Only":
                row["source_seq"] = ""



        # Sort Mapping rows by review priority while preserving the
        # original order inside each status group.
        status_priority = {
            "Mapped": 0,
            "Review Required": 1,
            "Source Only": 2,
            "Target Only": 3,
        }

        mapping_rows = [
            row
            for _, row in sorted(
                enumerate(mapping_rows),
                key=lambda item: (
                    status_priority.get(
                        item[1].get("mapping_status", ""),
                        99,
                    ),
                    item[0],
                ),
            )
        ]



        st.session_state[

            "mapping_df"

        ] = pd.DataFrame(

            mapping_rows,

            columns=MAPPING_GRID_COLUMNS,

        )



        # =========================

        # 4. Return Value

        # =========================

        if ai.return_values:

            return_rows = []



            for seq, item in enumerate(

                ai.return_values,

                start=1,

            ):

                return_rows.append(

                    {

                        "송신 시스템 / Source System":

                            item.source_system,

                        "순번 / Seq.":

                            seq,

                        "송신 테이블 / Source Table":

                            item.source_table,

                        "송신 PK / Source PK":

                            item.source_pk,

                        "송신 필드명 / Source Field":

                            item.source_field,

                        "송신 타입 / Source Type":

                            item.source_type,

                        "송신 사이즈 / Source Size":

                            item.source_size,

                        "송신 설명 / Source Description":

                            item.source_description,

                        "송신 비고 / Source Remark":

                            item.source_remark,

                        "Mapping / Mapping":

                            "<-",

                        "수신 시스템 / Target System":

                            item.target_system,

                        "수신 테이블 / Target Table":

                            item.target_table,

                        "수신 PK / Target PK":

                            item.target_pk,

                        "수신 필드명 / Target Field":

                            item.target_field,

                        "수신 타입 / Target Type":

                            item.target_type,

                        "수신 사이즈 / Target Size":

                            item.target_size,

                        "수신 설명 / Target Description":

                            item.target_description,

                        "수신 비고 / Target Remark":

                            item.target_remark,

                    }

                )



            st.session_state[

                "return_value_df"

            ] = pd.DataFrame(

                return_rows,

                columns=RETURN_VALUE_COLUMNS,

            )



        else:

            st.session_state[

                "return_value_df"

            ] = build_return_df()



        # Refresh editors / AgGrid

        st.session_state[

            "editor_version"

        ] += 1



        st.rerun()





# =========================

# Four front-end sections

# =========================

version = st.session_state[

    "editor_version"

]





# 1. Interface Information

st.header(

    "1. Interface Information"

)



edited = st.data_editor(

    st.session_state[

        "interface_info_df"

    ],

    use_container_width=True,

    hide_index=True,

    num_rows="fixed",

    column_config=(

        make_text_column_config(

            INTERFACE_INFO_UI_LABELS

        )

    ),

    key=(

        f"interface_info_editor_"

        f"{version}"

    ),

)



st.session_state[

    "interface_info_df"

] = edited





# 2. Transmission Information

st.header(

    "2. Transmission Information"

)



left, right = st.columns(2)



with left:

    st.subheader(

        "Source Side"

    )



    edited = st.data_editor(

        st.session_state[

            "source_transmission_df"

        ],

        use_container_width=True,

        hide_index=True,

        num_rows="fixed",

        column_config=(

            make_text_column_config(

                SOURCE_TRANSMISSION_UI_LABELS

            )

        ),

        key=(

            f"source_transmission_editor_"

            f"{version}"

        ),

    )



    st.session_state[

        "source_transmission_df"

    ] = edited





with right:

    st.subheader(

        "Target Side"

    )



    edited = st.data_editor(

        st.session_state[

            "target_transmission_df"

        ],

        use_container_width=True,

        hide_index=True,

        num_rows="fixed",

        column_config=(

            make_text_column_config(

                TARGET_TRANSMISSION_UI_LABELS

            )

        ),

        key=(

            f"target_transmission_editor_"

            f"{version}"

        ),

    )



    st.session_state[

        "target_transmission_df"

    ] = edited





# 3. Mapping Specification

st.header(

    "3. Mapping Specification"

)



st.caption(

    "Edit the mapping if needed. "

    "Status is generated automatically "

    "from the mapping result."

)


# =========================
# Mapping Summary / Review UI
# =========================
mapping_summary_df = st.session_state.get("mapping_df", pd.DataFrame()).copy()

if not mapping_summary_df.empty:
    if "review_reason" not in mapping_summary_df.columns:
        mapping_summary_df["review_reason"] = ""

    status_series = mapping_summary_df.get(
        "mapping_status",
        pd.Series("", index=mapping_summary_df.index),
    ).fillna("")

    review_reason_series = mapping_summary_df["review_reason"].fillna("").astype(str)

    def _reason_row_count(reason):
        return int(
            review_reason_series.map(
                lambda value: reason in [
                    part.strip()
                    for part in value.split(";")
                    if part.strip()
                ]
            ).sum()
        )

    multiple_reason_count = int(
        review_reason_series.map(
            lambda value: len(
                [part for part in value.split(";") if part.strip()]
            ) >= 2
        ).sum()
    )

    status_metrics = [
        ("Mapped", int((status_series == "Mapped").sum())),
        ("Review Required", int((status_series == "Review Required").sum())),
        ("Source Only", int((status_series == "Source Only").sum())),
        ("Target Only", int((status_series == "Target Only").sum())),
    ]

    reason_metrics = [
        ("Reference Conflict", _reason_row_count("Reference Conflict")),
        ("Low Confidence", _reason_row_count("Low Confidence")),
        ("Transform Required", _reason_row_count("Transform Required")),
        ("Format Conversion", _reason_row_count("Format Conversion")),
        ("Multiple Reasons", multiple_reason_count),
    ]

    st.markdown("### **Mapping Summary**")

    # Light visual card treatment for summary sections.
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 10px;
        }

        .mapping-summary-card-title {
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 0.35rem;
        }

        .mapping-summary-note {
            opacity: 0.68;
            font-size: 0.82rem;
            margin-top: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown(
            '<div class="mapping-summary-card-title">Status</div>',
            unsafe_allow_html=True,
        )
        status_cols = st.columns(4)
        for column, (label, value) in zip(status_cols, status_metrics):
            column.metric(label, value)

    with st.container(border=True):
        st.markdown(
            '<div class="mapping-summary-card-title">Review Reason</div>',
            unsafe_allow_html=True,
        )
        reason_cols = st.columns(5)
        for column, (label, value) in zip(reason_cols, reason_metrics):
            column.metric(label, value)

        st.markdown(
            '<div class="mapping-summary-note">'
            'Review Reason counts are row-based; one row may appear in multiple categories.'
            '</div>',
            unsafe_allow_html=True,
        )

    review_rows_df = mapping_summary_df[
        mapping_summary_df["mapping_status"] == "Review Required"
    ].copy()

    if not review_rows_df.empty:
        with st.expander(
            f"View Review Reasons ({len(review_rows_df)} rows)"
        ):
            review_display = pd.DataFrame(
                {
                    "Source Field": review_rows_df.get(
                        "source_field", pd.Series("", index=review_rows_df.index)
                    ),
                    "Target Field": review_rows_df.get(
                        "target_field", pd.Series("", index=review_rows_df.index)
                    ),
                    "Status": review_rows_df.get(
                        "mapping_status", pd.Series("", index=review_rows_df.index)
                    ),
                    "Review Reason": review_rows_df.get(
                        "review_reason", pd.Series("", index=review_rows_df.index)
                    ),
                    "Confidence": review_rows_df.get(
                        "confidence", pd.Series("", index=review_rows_df.index)
                    ),
                    "Details": review_rows_df.get(
                        "ai_reason", pd.Series("", index=review_rows_df.index)
                    ),
                }
            )
            st.dataframe(
                review_display,
                width="stretch",
                hide_index=True,
            )

st.markdown("### **Mapping Result**")

edited_mapping_df = (

    render_mapping_grid(

        st.session_state[

            "mapping_df"

        ],

        height=420,

        key=(

            f"mapping_grid_"

            f"{version}"

        ),

    )

)



st.session_state[

    "mapping_df"

] = edited_mapping_df





# 4. Return Value

st.header(

    "4. Return Value"

)



edited = st.data_editor(

    st.session_state[

        "return_value_df"

    ],

    use_container_width=True,

    hide_index=True,

    num_rows="dynamic",

    column_config={

        **make_text_column_config(

            RETURN_VALUE_UI_LABELS

        ),

        "순번 / Seq.":

            st.column_config.NumberColumn(

                "Seq."

            ),

    },

    key=(

        f"return_value_editor_"

        f"{version}"

    ),

)



st.session_state[

    "return_value_df"

] = edited


# =========================
# Deferred Workspace Action
# =========================
# Project controls are rendered near the top of the page, while editable
# tables (especially Mapping Result) are rendered later. Therefore destructive
# actions must be evaluated only here, after all current edits have been
# synchronized into st.session_state.
# This checks Python-side values; it does not acknowledge browser Grid delivery.
_handle_registry_navigation_request()

pending_workspace_action = st.session_state.get(
    "pending_workspace_action",
    "",
)
pending_workspace_payload = dict(
    st.session_state.get(
        "pending_workspace_payload",
        {},
    )
    or {}
)

if pending_workspace_action:
    _clear_pending_workspace_action()

    if _workspace_has_unsaved_changes():
        _request_unsaved_guard(
            pending_workspace_action,
            pending_workspace_payload,
        )
        st.rerun()

    # No unsaved changes: execute the requested action immediately.
    if pending_workspace_action == GUARD_ACTION_NEW_PROJECT:
        _clear_active_workspace()
        st.session_state["clear_saved_project_selector"] = True
        st.session_state["project_toast_message"] = (
            "New project workspace created."
        )
        st.session_state["project_toast_icon"] = "✅"
        st.rerun()

    elif pending_workspace_action == GUARD_ACTION_LOAD_PROJECT:
        target_project_id = pending_workspace_payload.get(
            "project_id",
            "",
        )
        try:
            loaded_project = load_project(target_project_id)
            _restore_project_workspace(loaded_project)
            st.session_state["force_project_selector_id"] = (
                target_project_id
            )
            st.session_state["project_toast_message"] = (
                "Project loaded successfully."
            )
            st.session_state["project_toast_icon"] = "✅"
            st.rerun()
        except Exception as e:
            st.error(f"Failed to load project: {e}")

    elif pending_workspace_action == GUARD_ACTION_DELETE_PROJECT:
        st.session_state["project_delete_mode"] = True
        st.rerun()

    elif pending_workspace_action == GUARD_ACTION_REGENERATE_MAPPING:
        st.session_state["generate_mapping_requested"] = True
        st.rerun()


# =========================
# Deferred Project Save
# =========================
# Save runs here, after every editable section has synchronized its latest
# value into session_state.
if st.session_state.get("project_save_requested", False):
    st.session_state["project_save_requested"] = False

    current_project_id = str(
        st.session_state.get("current_project_id", "")
        or ""
    ).strip()

    # For a brand-new workspace, only save when there is real user work.
    # Existing projects may still be saved based on digest comparison below.
    if (
        not current_project_id
        and not _workspace_has_meaningful_content()
    ):
        # If this save was requested only as part of a guarded follow-up
        # action (e.g. Save Current & Load) and there is actually nothing
        # to save, skip the save and continue the requested action.
        post_save_action = st.session_state.pop(
            "after_save_guard_action",
            "",
        )
        post_save_payload = st.session_state.pop(
            "after_save_guard_payload",
            {},
        )

        if post_save_action == GUARD_ACTION_LOAD_PROJECT:
            target_id = post_save_payload.get(
                "project_id",
                "",
            )
            try:
                loaded_project = load_project(target_id)
                _restore_project_workspace(loaded_project)
                st.session_state[
                    "force_project_selector_id"
                ] = target_id
                st.session_state[
                    "project_toast_message"
                ] = "Project loaded successfully."
                st.session_state[
                    "project_toast_icon"
                ] = "✅"
                st.rerun()
            except Exception as load_error:
                st.error(
                    f"Failed to load project: {load_error}"
                )

        elif post_save_action == GUARD_ACTION_NEW_PROJECT:
            _clear_active_workspace()
            st.session_state[
                "clear_saved_project_selector"
            ] = True
            st.session_state[
                "project_toast_message"
            ] = "New project workspace created."
            st.session_state[
                "project_toast_icon"
            ] = "✅"
            st.rerun()

        elif post_save_action == GUARD_ACTION_REGENERATE_MAPPING:
            st.session_state[
                "generate_mapping_requested"
            ] = True
            st.rerun()

        else:
            st.session_state["project_toast_message"] = (
                "There are no changes to save."
            )
            st.session_state["project_toast_icon"] = "ℹ️"
            st.rerun()

    current_digest = _current_workspace_digest()
    last_saved_digest = str(
        st.session_state.get("last_saved_workspace_digest", "")
        or ""
    ).strip()

    # Existing project + unchanged editable workspace = no write needed.
    if (
        current_project_id
        and last_saved_digest
        and current_digest == last_saved_digest
    ):
        st.session_state["project_toast_message"] = (
            "No changes to save."
        )
        st.session_state["project_toast_icon"] = "ℹ️"
        st.rerun()

    project_name = str(
        st.session_state.get("project_name", "")
        or ""
    ).strip()

    if not project_name:
        project_name = build_default_project_name()

    if current_project_id:
        metadata = {
            "project_id": current_project_id,
            "project_name": project_name,
            "created_at": st.session_state.get(
                "current_project_created_at",
                "",
            ),
            "last_saved_at": st.session_state.get(
                "project_last_saved_at",
                "",
            ),
        }
    else:
        metadata = create_project_metadata(
            project_name=project_name,
        )

    # Raw uploaded files are intentionally NOT stored.
    source_uploaded = st.session_state.get(
        "source_structure_file"
    )
    target_uploaded = st.session_state.get(
        "target_structure_file"
    )

    metadata["source_structure_type"] = (
        get_structure_type(source_uploaded)
        if source_uploaded is not None
        else ""
    )
    metadata["target_structure_type"] = (
        get_structure_type(target_uploaded)
        if target_uploaded is not None
        else ""
    )

    if source_uploaded is not None:
        metadata["source_file_name"] = getattr(
            source_uploaded,
            "name",
            "",
        )
        try:
            metadata["source_file_hash"] = hashlib.sha256(
                source_uploaded.getvalue()
            ).hexdigest()
        except Exception:
            metadata["source_file_hash"] = ""

    if target_uploaded is not None:
        metadata["target_file_name"] = getattr(
            target_uploaded,
            "name",
            "",
        )
        try:
            metadata["target_file_hash"] = hashlib.sha256(
                target_uploaded.getvalue()
            ).hexdigest()
        except Exception:
            metadata["target_file_hash"] = ""

    project_snapshot = build_project_snapshot(
        metadata=metadata,
        interface_info_df=st.session_state.get(
            "interface_info_df"
        ),
        source_transmission_df=st.session_state.get(
            "source_transmission_df"
        ),
        target_transmission_df=st.session_state.get(
            "target_transmission_df"
        ),
        mapping_df=st.session_state.get(
            "mapping_df"
        ),
        return_value_df=st.session_state.get(
            "return_value_df"
        ),
        reference_review_conflicts=st.session_state.get(
            "reference_review_conflicts",
            [],
        ),
    )

    try:
        save_result = save_project(project_snapshot)

        st.session_state["current_project_id"] = (
            save_result["project_id"]
        )
        st.session_state["current_project_created_at"] = (
            metadata.get("created_at", "")
        )
        st.session_state["project_name"] = (
            save_result["project_name"]
        )
        st.session_state["project_last_saved_at"] = (
            save_result["last_saved_at"]
        )
        st.session_state["last_saved_workspace_digest"] = (
            current_digest
        )

        # Keep newly saved/current project selected after rerun.
        post_save_action = st.session_state.pop(
            "after_save_guard_action",
            "",
        )
        post_save_payload = st.session_state.pop(
            "after_save_guard_payload",
            {},
        )

        if post_save_action == GUARD_ACTION_NEW_PROJECT:
            _clear_active_workspace()
            st.session_state[
                "clear_saved_project_selector"
            ] = True
            st.session_state[
                "project_toast_message"
            ] = (
                "Your changes were saved. "
                "A new project workspace is ready."
            )
            st.session_state[
                "project_toast_icon"
            ] = "✅"
            st.rerun()

        elif post_save_action == GUARD_ACTION_LOAD_PROJECT:
            target_id = post_save_payload.get(
                "project_id",
                "",
            )
            try:
                loaded_project = load_project(
                    target_id
                )
                _restore_project_workspace(
                    loaded_project
                )
                st.session_state[
                    "force_project_selector_id"
                ] = target_id
                st.session_state[
                    "project_toast_message"
                ] = (
                    "Your changes were saved, and the selected "
                    "project was loaded."
                )
                st.session_state[
                    "project_toast_icon"
                ] = "✅"
                st.rerun()
            except Exception as load_error:
                st.session_state[
                    "force_project_selector_id"
                ] = save_result["project_id"]
                st.session_state[
                    "project_toast_message"
                ] = (
                    "Your changes were saved, but the selected "
                    f"project could not be loaded: {load_error}"
                )
                st.session_state[
                    "project_toast_icon"
                ] = "⚠️"
                st.rerun()

        elif post_save_action == GUARD_ACTION_REGENERATE_MAPPING:
            st.session_state[
                "force_project_selector_id"
            ] = save_result["project_id"]
            st.session_state[
                "generate_mapping_requested"
            ] = True
            st.session_state[
                "project_toast_message"
            ] = (
                "Your changes were saved. Regenerating Mapping..."
            )
            st.session_state[
                "project_toast_icon"
            ] = "✅"
            st.rerun()

        else:
            st.session_state[
                "force_project_selector_id"
            ] = save_result["project_id"]
            st.session_state[
                "project_toast_message"
            ] = "Your changes have been saved."
            st.session_state[
                "project_toast_icon"
            ] = "✅"
            st.rerun()

    except Exception as e:
        st.error(
            f"Failed to save project: {e}"
        )



# 5. Export Excel

st.header(

    "5. Export Excel"

)



st.caption(

    "Download the reviewed Mapping Specification in English or Korean."

)



try:

    export_mapping_df = build_export_mapping_df(

        st.session_state["mapping_df"]

    )



    english_excel_bytes = create_interface_mapping_excel(

        interface_info_df=st.session_state["interface_info_df"],

        source_transmission_df=st.session_state["source_transmission_df"],

        target_transmission_df=st.session_state["target_transmission_df"],

        mapping_df=export_mapping_df,

        return_value_df=st.session_state["return_value_df"],

        language="en",

    )



    korean_excel_bytes = create_interface_mapping_excel(

        interface_info_df=st.session_state["interface_info_df"],

        source_transmission_df=st.session_state["source_transmission_df"],

        target_transmission_df=st.session_state["target_transmission_df"],

        mapping_df=export_mapping_df,

        return_value_df=st.session_state["return_value_df"],

        language="ko",

    )



    download_left, download_right = st.columns(2)



    with download_left:

        st.download_button(

            label="⬇️ Download English Excel",

            data=english_excel_bytes,

            file_name="Interface_Mapping_Specification_Preview.xlsx",

            mime=(

                "application/vnd.openxmlformats-officedocument."

                "spreadsheetml.sheet"

            ),

            type="primary",

            use_container_width=True,

        )



    with download_right:

        st.download_button(

            label="⬇️ 한국어 Excel 다운로드",

            data=korean_excel_bytes,

            file_name="인터페이스 매핑 정의서.xlsx",

            mime=(

                "application/vnd.openxmlformats-officedocument."

                "spreadsheetml.sheet"

            ),

            use_container_width=True,

        )



except Exception as e:

    st.error(

        f"Failed to prepare Excel download: {e}"

    )
