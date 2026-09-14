import pandas as pd
from st_aggrid import AgGrid, JsCode


# =========================
# Status cell style
# =========================
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

    if (params.value === 'Source Only') {
        return {
            backgroundColor: '#FDE2E2',
            color: '#B71C1C',
            fontWeight: '700',
            textAlign: 'center'
        };
    }

    if (params.value === 'Target Only') {
        return {
            backgroundColor: '#FDE2E2',
            color: '#B71C1C',
            fontWeight: '700',
            textAlign: 'center'
        };
    }

    if (params.value === 'Review Required') {
        return {
            backgroundColor: '#FFF3CD',
            color: '#856404',
            fontWeight: '700',
            textAlign: 'center'
        };
    }

    return {};
}
""")


# =========================
# Column definitions
# =========================
COLUMN_DEFS = [
    {
        "headerName": "Source",
        "headerClass": "main-group-header",
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
                "headerTooltip": "Enter manually if table information is unavailable.",
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
            },
            {
                "headerName": "Remark",
                "field": "source_remark",
                "editable": True,
                "width": 180,
                "headerTooltip": "For manual remarks.",
            },
        ],
    },

    # =========================
    # Mapping
    # =========================
    {
        "headerName": "",
        "children": [
            {
                "headerName": "Mapping",
                "field": "mapping",
                "editable": False,
                "width": 90,
            },
            {
                "headerName": "Status",
                "field": "mapping_status",
                "editable": False,
                "width": 130,
                "cellStyle": STATUS_CELL_STYLE,
            },
        ],
    },

    # =========================
    # Target
    # =========================
    {
        "headerName": "Target",
        "headerClass": "main-group-header",
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
                "headerTooltip": "Enter manually if table information is unavailable.",
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
            },
            {
                "headerName": "Remark",
                "field": "target_remark",
                "editable": True,
                "width": 180,
                "headerTooltip": "For manual remarks.",
            },
        ],
    },
]


# =========================
# Custom CSS
# =========================
CUSTOM_CSS = {
    ".main-group-header .ag-header-group-cell-label": {
        "justify-content": "center",
        "font-weight": "700",
        "font-size": "18px",
    },
}


# =========================
# Render Mapping Grid
# =========================
def render_mapping_grid(
    mapping_df: pd.DataFrame,
    height: int = 420,
    key: str = "mapping_grid",
) -> pd.DataFrame:
    """
    Render the Mapping Specification table.

    Source:
    System / Seq. / Table / PK / Field Name /
    Type / Size / Description / Remark

    Mapping:
    Mapping / Status

    Target:
    System / Table / PK / Field Name /
    Type / Size / Description / Remark
    """

    grid_options = {
        "columnDefs": COLUMN_DEFS,
        "defaultColDef": {
            "resizable": True,
            "sortable": False,
            "filter": False,
        },
        "rowHeight": 42,
        "headerHeight": 42,
        "groupHeaderHeight": 42,
    }

    response = AgGrid(
        mapping_df,
        gridOptions=grid_options,
        height=height,
        fit_columns_on_grid_load=False,
        theme="streamlit",
        custom_css=CUSTOM_CSS,
        allow_unsafe_jscode=True,
        key=key,
    )

    edited_data = response["data"]

    if isinstance(edited_data, pd.DataFrame):
        return edited_data

    return pd.DataFrame(edited_data)