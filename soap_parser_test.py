import pandas as pd
import streamlit as st

from parsers.soap_parser import (
    build_soap_ai_payload,
    read_soap_xml_file,
)


st.set_page_config(
    page_title="SOAP Parser Test",
    page_icon="🧪",
    layout="wide",
)

st.title("🧪 SOAP Parser Test")
st.caption(
    "Test XML / WSDL / XSD parsing before connecting Claude AI."
)


# =========================
# Upload
# =========================
uploaded_file = st.file_uploader(
    "Upload SOAP / XML File",
    type=["xml", "wsdl", "xsd"],
)


if uploaded_file is not None:
    try:
        parsed = read_soap_xml_file(
            uploaded_file
        )

    except Exception as e:
        st.error(
            f"Failed to parse file: {e}"
        )
        st.stop()

    # =========================
    # 1. Document Summary
    # =========================
    st.header("1. Document Summary")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Document Type",
            parsed["document_type"],
        )

    with col2:
        st.metric(
            "Root Element",
            parsed["root"],
        )

    # =========================
    # 2. Namespaces
    # =========================
    st.header("2. Namespaces")

    namespaces = parsed.get(
        "namespaces",
        {},
    )

    if namespaces:
        namespace_df = pd.DataFrame(
            [
                {
                    "Prefix": prefix,
                    "Namespace URI": uri,
                }
                for prefix, uri
                in namespaces.items()
            ]
        )

        st.dataframe(
            namespace_df,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            "No namespace declarations found."
        )

    # =========================
    # 3. Parsed Elements
    # =========================
    st.header("3. Parsed Elements")

    elements = parsed.get(
        "elements",
        [],
    )

    if elements:
        element_df = pd.DataFrame(
            elements
        )

        st.dataframe(
            element_df,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.warning(
            "No XML elements were found."
        )

    # =========================
    # 4. AI Payload Preview
    # =========================
    st.header("4. AI Payload Preview")

    ai_payload = build_soap_ai_payload(
        parsed
    )

    st.json(
        ai_payload
    )

    with st.expander(
        "Raw Parsed Result"
    ):
        st.json(
            parsed
        )
