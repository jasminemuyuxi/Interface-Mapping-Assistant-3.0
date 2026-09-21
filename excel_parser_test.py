import json

import pandas as pd
import streamlit as st

from parsers.excel_parser import (
    build_excel_ai_payload,
    read_excel_file,
)
from services.document_ai_service import analyze_document_payload


st.set_page_config(
    page_title="Excel Parser Test",
    layout="wide",
)

st.title("Excel Parser Test")

# =========================
# Document Role
# =========================
role = st.radio(
    "Document Role",
    options=["source", "target"],
    horizontal=True,
    help=(
        "Choose whether this document represents "
        "the Source or Target interface."
    ),
)

# =========================
# Upload Excel
# =========================
uploaded_file = st.file_uploader(
    "Upload Excel File",
    type=["xlsx", "xlsm"],
)

if uploaded_file is not None:
    try:
        # =========================
        # 1. Parse Excel
        # =========================
        sheets = read_excel_file(uploaded_file)

        st.success(
            f"Successfully parsed {len(sheets)} sheet(s)."
        )

        # =========================
        # 2. Excel table preview
        # =========================
        st.header("1. Excel Preview")

        for sheet in sheets:
            st.subheader(sheet["sheet_name"])

            rows = sheet["rows"]

            if not rows:
                st.info("This sheet is empty.")
                continue

            max_columns = max(len(row) for row in rows)

            normalized_rows = []

            for row in rows:
                normalized_row = row + (
                    [""] * (max_columns - len(row))
                )
                normalized_rows.append(normalized_row)

            columns = [
                f"Column {index + 1}"
                for index in range(max_columns)
            ]

            df = pd.DataFrame(
                normalized_rows,
                columns=columns,
            )

            # Remove fully empty columns
            df = df.loc[
                :,
                (df != "").any(axis=0),
            ]

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                height=450,
            )

        # =========================
        # 3. Build AI-friendly payload
        # =========================
        ai_payload = build_excel_ai_payload(sheets)

        st.header("2. AI Payload Preview")

        st.caption(
            "Empty cells are removed, while cell positions "
            "and values are preserved."
        )

        st.json(ai_payload)

        with st.expander("View Raw JSON"):
            st.code(
                json.dumps(
                    ai_payload,
                    ensure_ascii=False,
                    indent=2,
                ),
                language="json",
            )

        # =========================
        # 4. Claude document analysis
        # =========================
        st.header("3. Claude Document Analysis")

        if st.button(
            "Analyze with Claude",
            type="primary",
        ):
            with st.spinner(
                f"Claude is analyzing the {role} side..."
            ):
                result = analyze_document_payload(
                    document_payload=ai_payload,
                    role=role,
                    file_name=uploaded_file.name,
                )

            st.session_state["excel_ai_result"] = result

        if "excel_ai_result" in st.session_state:
            result = st.session_state["excel_ai_result"]

            st.subheader("Interface Information")

            info_df = pd.DataFrame(
                [
                    {
                        "Interface ID": result["interface_id"],
                        "Interface Name": result["interface_name"],
                    }
                ]
            )

            st.dataframe(
                info_df,
                use_container_width=True,
                hide_index=True,
            )

            st.subheader("Extracted Fields")

            fields = result["fields"]

            if fields:
                fields_df = pd.DataFrame(fields)

                st.dataframe(
                    fields_df,
                    use_container_width=True,
                    hide_index=True,
                    height=500,
                )
            else:
                st.info(
                    "No interface fields were extracted."
                )

            with st.expander("View AI Result JSON"):
                st.json(result)

    except Exception as e:
        st.error(f"Failed to process Excel: {e}")
