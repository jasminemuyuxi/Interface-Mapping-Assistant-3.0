import re

import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, JsCode


STATUS_CELL_STYLE = JsCode("""
function(params) {
    if (params.value === 'Mapped') {
        return {
            backgroundColor: '#DFF2E1',
            color: '#1B5E20',
            fontWeight: '700',
            textAlign: 'center'
        };
    }

    if (
        params.value === 'Source Only' ||
        params.value === 'Target Only'
    ) {
        return {
            backgroundColor: '#FDE2E2',
            color: '#B71C1C',
            fontWeight: '700',
            textAlign: 'center'
        };
    }

    if (params.value === 'Review Required') {
        return {
            backgroundColor: '#FFF4CC',
            color: '#8A6D1D',
            fontWeight: '700',
            textAlign: 'center'
        };
    }

    return {
        textAlign: 'center'
    };
}
""")


CUSTOM_CSS = {
    ".main-group-header .ag-header-group-cell-label": {
        "justify-content": "center",
        "font-weight": "700",
        "font-size": "18px",
    },
}


def _build_hierarchy(path):
    """Build parent hierarchy from a full internal Path."""
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


def _ensure_hierarchy_columns(mapping_df: pd.DataFrame) -> pd.DataFrame:
    """
    Backward-compatible helper for older session_state DataFrames.

    New mappings persist Hierarchy directly. If an older DataFrame does not
    have those columns yet, derive them once from source_path / target_path.
    """
    grid_df = mapping_df.copy()

    if "source_hierarchy" not in grid_df.columns:
        grid_df["source_hierarchy"] = (
            grid_df.get(
                "source_path",
                pd.Series("", index=grid_df.index),
            )
            .fillna("")
            .map(_build_hierarchy)
        )

    if "target_hierarchy" not in grid_df.columns:
        grid_df["target_hierarchy"] = (
            grid_df.get(
                "target_path",
                pd.Series("", index=grid_df.index),
            )
            .fillna("")
            .map(_build_hierarchy)
        )

    return grid_df


COLUMN_DEFS = [
    {
        "headerName": "Source",
        "headerClass": "main-group-header",
        # Keep Source columns married: users may reorder inside Source,
        # but a Source child column cannot be dragged into another group.
        "marryChildren": True,
        "children": [
            {
                "headerName": "System",
                "field": "source_system",
                "editable": True,
                "width": 120,
            },
            {
                "headerName": "Seq.",
                "field": "source_seq",
                "editable": False,
                "width": 80,
            },
            {
                "headerName": "Table",
                "field": "source_table",
                "editable": True,
                "width": 130,
                "headerTooltip": (
                    "Manual entry. Table name is not inferred automatically."
                ),
            },
            {
                "headerName": "PK",
                "field": "source_pk",
                "editable": True,
                "width": 80,
            },
            {
                "headerName": "Hierarchy",
                "field": "source_hierarchy",
                "editable": True,
                "width": 260,
                "tooltipField": "source_hierarchy",
                "headerTooltip": (
                    "Parent field hierarchy derived from Path. "
                    "You can edit it before export."
                ),
            },
            {
                "headerName": "Field Name",
                "field": "source_field",
                "editable": True,
                "width": 160,
            },
            {
                "headerName": "Type",
                "field": "source_type",
                "editable": True,
                "width": 110,
            },
            {
                "headerName": "Size",
                "field": "source_size",
                "editable": True,
                "width": 90,
            },
            {
                "headerName": "Description",
                "field": "source_description",
                "editable": True,
                "width": 220,
                "tooltipField": "source_description",
            },
            {
                "headerName": "Remark",
                "field": "source_remark",
                "editable": True,
                "width": 180,
                "headerTooltip": "Manual entry.",
            },
        ],
    },
    {
        "headerName": "Mapping Review",
        "headerClass": "main-group-header",
        # Keep Mapping / Status as their own fixed logical group boundary.
        "marryChildren": True,
        "children": [
            {
                "headerName": "Mapping",
                "field": "mapping",
                "editable": False,
                "width": 100,
            },
            {
                "headerName": "Status",
                "field": "mapping_status",
                "editable": False,
                "width": 140,
                "cellStyle": STATUS_CELL_STYLE,
            },
            {
                "headerName": "Review Reason",
                "field": "review_reason",
                "editable": False,
                "width": 230,
                "tooltipField": "review_reason",
                "headerTooltip": (
                    "Why this row requires review. Multiple reasons are "
                    "separated by semicolons."
                ),
            },
        ],
    },
    {
        "headerName": "Target",
        "headerClass": "main-group-header",
        # Keep Target columns married: users may reorder inside Target,
        # but a Target child column cannot be dragged into another group.
        "marryChildren": True,
        "children": [
            {
                "headerName": "System",
                "field": "target_system",
                "editable": True,
                "width": 120,
            },
            {
                "headerName": "Table",
                "field": "target_table",
                "editable": True,
                "width": 130,
                "headerTooltip": (
                    "Manual entry. Table name is not inferred automatically."
                ),
            },
            {
                "headerName": "PK",
                "field": "target_pk",
                "editable": True,
                "width": 80,
            },
            {
                "headerName": "Hierarchy",
                "field": "target_hierarchy",
                "editable": True,
                "width": 260,
                "tooltipField": "target_hierarchy",
                "headerTooltip": (
                    "Parent field hierarchy derived from Path. "
                    "You can edit it before export."
                ),
            },
            {
                "headerName": "Field Name",
                "field": "target_field",
                "editable": True,
                "width": 160,
            },
            {
                "headerName": "Type",
                "field": "target_type",
                "editable": True,
                "width": 110,
            },
            {
                "headerName": "Size",
                "field": "target_size",
                "editable": True,
                "width": 90,
            },
            {
                "headerName": "Description",
                "field": "target_description",
                "editable": True,
                "width": 220,
                "tooltipField": "target_description",
            },
            {
                "headerName": "Remark",
                "field": "target_remark",
                "editable": True,
                "width": 180,
                "headerTooltip": "Manual entry.",
            },
        ],
    },
]


SET_FILTER_FIELDS = {
    "source_system",
    "source_table",
    "source_pk",
    "source_type",
    "mapping",
    "mapping_status",
    "review_reason",
    "target_system",
    "target_table",
    "target_pk",
    "target_type",
}

TEXT_FILTER_FIELDS = {
    "source_hierarchy",
    "source_field",
    "source_description",
    "source_remark",
    "target_hierarchy",
    "target_field",
    "target_description",
    "target_remark",
}


def _apply_excel_like_filters(column_defs):
    """Return a copy of column definitions with Excel-like filters applied."""
    result = []

    for definition in column_defs:
        item = dict(definition)

        if "children" in item:
            item["children"] = _apply_excel_like_filters(item["children"])
            result.append(item)
            continue

        field = item.get("field")

        if field in SET_FILTER_FIELDS:
            # AG Grid Set Filter gives an Excel-like checklist of distinct values.
            item["filter"] = "agSetColumnFilter"
            item["filterParams"] = {
                "excelMode": "windows",
                "buttons": ["reset"],
                "closeOnApply": False,
            }
        elif field in TEXT_FILTER_FIELDS:
            item["filter"] = "agTextColumnFilter"
            item["filterParams"] = {
                "buttons": ["reset"],
                "defaultOption": "contains",
                "closeOnApply": True,
            }
        elif field == "source_seq":
            item["filter"] = "agNumberColumnFilter"
            item["filterParams"] = {
                "buttons": ["reset"],
                "closeOnApply": True,
            }

        result.append(item)

    return result


def render_mapping_grid(
    mapping_df: pd.DataFrame,
    height: int = 420,
    key: str = "mapping_grid",
) -> pd.DataFrame:
    """
    Render the editable Mapping Specification grid.

    Hierarchy is now a normal persistent page value for every interface type.
    Flat structures simply show a blank Hierarchy cell.
    """
    grid_df = _ensure_hierarchy_columns(mapping_df)

    filtered_column_defs = _apply_excel_like_filters(COLUMN_DEFS)

    grid_options = {
        "columnDefs": filtered_column_defs,
        "defaultColDef": {
            "resizable": True,
            "sortable": True,
            "filter": "agTextColumnFilter",
            "floatingFilter": False,
            "filterParams": {
                "buttons": ["reset"],
                "defaultOption": "contains",
                "closeOnApply": True,
            },
        },
        "rowHeight": 42,
        "headerHeight": 42,
        "groupHeaderHeight": 42,
        "tooltipShowDelay": 200,

        # Critical for Save / Load / New Project safety:
        # if the user is still typing in an editable cell and clicks outside
        # the grid, AG Grid must commit the active editor before the page
        # action continues.
        "stopEditingWhenCellsLoseFocus": True,

        # Keep keyboard editing behavior predictable after committing a cell.
        "enterNavigatesVerticallyAfterEdit": True,
    }

    # Temporary stable row id lets us return the COMPLETE Mapping DataFrame
    # even though AgGrid sends back only the currently filtered rows.
    # This means filtering never deletes rows from session_state or Excel export.
    grid_df = grid_df.reset_index(drop=True).copy()
    grid_df["__row_id"] = range(len(grid_df))

    grid_options["columnDefs"] = [
        {
            "headerName": "",
            "field": "__row_id",
            "hide": True,
            "filter": False,
            "sortable": False,
            "suppressColumnsToolPanel": True,
        },
        *filtered_column_defs,
    ]

    # The placeholder is created before AgGrid so the count appears ABOVE the grid.
    filter_count_placeholder = st.empty()

    response = AgGrid(
        grid_df,
        gridOptions=grid_options,
        height=height,
        fit_columns_on_grid_load=False,
        theme="streamlit",
        custom_css=CUSTOM_CSS,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=True,
        data_return_mode="FILTERED_AND_SORTED",
        update_mode="MODEL_CHANGED",
        key=key,
    )

    filtered_df = pd.DataFrame(response.get("data", []))
    total_count = len(grid_df)
    filtered_count = len(filtered_df)

    if filtered_count == total_count:
        filter_count_placeholder.caption(
            f"Showing **{total_count}** of **{total_count}** rows"
        )
    else:
        filter_count_placeholder.caption(
            f"🔎 Filtered: **{filtered_count}** of **{total_count}** rows"
        )

    # Merge edits from the visible/filtered rows back into the full dataset.
    # Filtering therefore changes only what the user sees, not the underlying
    # Mapping result or the rows exported to Excel.
    full_df = grid_df.copy()

    if not filtered_df.empty and "__row_id" in filtered_df.columns:
        filtered_df = filtered_df.copy()
        filtered_df["__row_id"] = pd.to_numeric(
            filtered_df["__row_id"],
            errors="coerce",
        )

        for _, edited_row in filtered_df.dropna(subset=["__row_id"]).iterrows():
            row_id = int(edited_row["__row_id"])
            if 0 <= row_id < len(full_df):
                for column in full_df.columns:
                    if column == "__row_id" or column not in edited_row.index:
                        continue
                    full_df.at[row_id, column] = edited_row[column]

    return full_df.drop(columns=["__row_id"], errors="ignore")
