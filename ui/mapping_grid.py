import re

import pandas as pd
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
    """
    Convert a full Path into a readable parent hierarchy.

    Examples:
        Envelope.Body.Order.ConsigneeParty.InternalID
        -> Envelope > Body > Order > ConsigneeParty

        order.items[].product.code
        -> order > items[] > product

    If the path contains only the field itself, return "".
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


def _build_column_defs(
    show_source_hierarchy=False,
    show_target_hierarchy=False,
):
    source_children = [
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
    ]

    if show_source_hierarchy:
        source_children.append(
            {
                "headerName": "Hierarchy",
                "field": "source_hierarchy",
                "editable": False,
                "width": 260,
                "tooltipField": "source_hierarchy",
            }
        )

    source_children.extend(
        [
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
        ]
    )

    target_children = [
        {
            "headerName": "System",
            "field": "target_system",
            "editable": True,
            "width": 120,
        },
    ]

    if show_target_hierarchy:
        target_children.append(
            {
                "headerName": "Hierarchy",
                "field": "target_hierarchy",
                "editable": False,
                "width": 260,
                "tooltipField": "target_hierarchy",
            }
        )

    target_children.extend(
        [
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
        ]
    )

    return [
        {
            "headerName": "Source",
            "headerClass": "main-group-header",
            "children": source_children,
        },
        {
            "headerName": "",
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
            ],
        },
        {
            "headerName": "Target",
            "headerClass": "main-group-header",
            "children": target_children,
        },
    ]


def render_mapping_grid(
    mapping_df: pd.DataFrame,
    height: int = 420,
    key: str = "mapping_grid",
    show_source_hierarchy: bool = False,
    show_target_hierarchy: bool = False,
) -> pd.DataFrame:
    """
    Render the editable Mapping Specification grid.

    SOAP hierarchy is display-only:
    - Source hierarchy is derived from source_path.
    - Target hierarchy is derived from target_path.
    - Temporary hierarchy columns are removed again before returning,
      so the existing Mapping DataFrame / Excel export schema is unchanged.
    """
    grid_df = mapping_df.copy()

    temporary_columns = []

    if show_source_hierarchy:
        grid_df["source_hierarchy"] = (
            grid_df.get(
                "source_path",
                pd.Series("", index=grid_df.index),
            )
            .fillna("")
            .map(_build_hierarchy)
        )
        temporary_columns.append("source_hierarchy")

    if show_target_hierarchy:
        grid_df["target_hierarchy"] = (
            grid_df.get(
                "target_path",
                pd.Series("", index=grid_df.index),
            )
            .fillna("")
            .map(_build_hierarchy)
        )
        temporary_columns.append("target_hierarchy")

    grid_options = {
        "columnDefs": _build_column_defs(
            show_source_hierarchy=show_source_hierarchy,
            show_target_hierarchy=show_target_hierarchy,
        ),
        "defaultColDef": {
            "resizable": True,
            "sortable": False,
            "filter": False,
        },
        "rowHeight": 42,
        "headerHeight": 42,
        "groupHeaderHeight": 42,
        "tooltipShowDelay": 200,
    }

    response = AgGrid(
        grid_df,
        gridOptions=grid_options,
        height=height,
        fit_columns_on_grid_load=False,
        theme="streamlit",
        custom_css=CUSTOM_CSS,
        allow_unsafe_jscode=True,
        key=key,
    )

    edited_df = pd.DataFrame(response["data"])

    # Hierarchy is display-only. Keep the original mapping schema intact.
    edited_df = edited_df.drop(
        columns=[
            column
            for column in temporary_columns
            if column in edited_df.columns
        ],
        errors="ignore",
    )

    return edited_df
