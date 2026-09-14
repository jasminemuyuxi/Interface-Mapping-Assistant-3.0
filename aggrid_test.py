import pandas as pd
import streamlit as st

from mapping.mapping_service import build_mapping_rows
from ui.mapping_grid import render_mapping_grid


st.set_page_config(
    page_title="AgGrid Mapping Test",
    layout="wide",
)

st.title("Mapping Specification - AgGrid Test")


# =========================
# Test Source / Target Data
# =========================
source_fields = [
    {
        "System": "SAP",
        "PK": "PK",
        "Field": "ORDER_ID",
        "Type": "VARCHAR",
        "Size": "20",
        "Description": "Order ID",
    },
    {
        "System": "SAP",
        "PK": "",
        "Field": "LEGACY_FLAG",
        "Type": "VARCHAR",
        "Size": "1",
        "Description": "Legacy Flag",
    },
]

target_fields = [
    {
        "System": "WMS",
        "PK": "",
        "Field": "ORDER_NO",
        "Type": "VARCHAR2",
        "Size": "20",
        "Description": "Order Number",
    },
    {
        "System": "WMS",
        "PK": "",
        "Field": "WAREHOUSE_CODE",
        "Type": "VARCHAR2",
        "Size": "20",
        "Description": "Warehouse Code",
    },
]


# =========================
# Simulated AI Result
# =========================
ai_mappings = [
    {
        "source_field": "ORDER_ID",
        "target_field": "ORDER_NO",
    }
]


# =========================
# Build Mapping Data
# =========================
mapping_rows = build_mapping_rows(
    source_fields,
    target_fields,
    ai_mappings,
)

mapping_df = pd.DataFrame(mapping_rows)


# =========================
# Render Mapping Grid
# =========================
edited_mapping_df = render_mapping_grid(
    mapping_df,
    height=300,
    key="mapping_grid_test",
)
