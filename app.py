import hashlib
import json
import os
from datetime import date
from pathlib import Path as FilePath

import pandas as pd
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from exporters.excel_exporter import create_interface_mapping_excel
from mapping.mapping_service import build_mapping_rows
from parsers.excel_parser import (
    build_excel_ai_payload,
    read_excel_file,
)
from parsers.json_parser import flatten_json
from parsers.soap_parser import (
    build_soap_ai_payload,
    read_soap_xml_file,
)
from services.document_ai_service import analyze_document_payload
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


# =========================
# File helpers
# =========================
def read_json_file(uploaded_file):
    raw = uploaded_file.getvalue().decode("utf-8-sig")
    return json.loads(raw)


def get_file_extension(uploaded_file):
    return FilePath(uploaded_file.name).suffix.lower()


def get_allowed_file_types(interface_type):
    return {
        "JSON": ["json"],
        "File": [
            "pdf",
            "docx",
            "xlsx",
            "xls",
            "xlsm",
            "png",
            "jpg",
            "jpeg",
            "webp",
            "bmp",
            "tif",
            "tiff",
        ],
        "Swagger": ["json", "yaml", "yml"],
        "EDI": ["edi", "txt"],
        "Open API": ["json", "yaml", "yml"],
        "SOAP": [
            "xml",
            "wsdl",
            "xsd",
            "json",
            "xlsx",
            "xls",
            "xlsm",
        ],
        "Other": None,
    }.get(interface_type)


def normalize_standard_fields(fields):
    """
    Normalize fields from different parsers into the shared structure.

    Path is an internal identifier used for reliable mapping.
    If a document does not provide a path, Field is used as the
    internal fallback path.
    """
    normalized = []

    for field in fields:
        field_name = str(field.get("Field", "") or "").strip()

        if not field_name:
            continue

        path = str(field.get("Path", "") or "").strip()

        normalized.append(
            {
                "Path": path or field_name,
                "Field": field_name,
                "System": str(field.get("System", "") or "").strip(),
                "PK": str(field.get("PK", "") or "").strip(),
                "Type": str(field.get("Type", "") or "").strip(),
                "Size": str(field.get("Size", "") or "").strip(),
                "Description": str(
                    field.get("Description", "") or ""
                ).strip(),
                "Sample": str(field.get("Sample", "") or "").strip(),
            }
        )

    return normalized


def analyze_uploaded_interface(
    uploaded_file,
    interface_type,
    role,
):
    """
    Convert one uploaded interface into the shared field structure.

    JSON:
        JSON parser.

    File + Excel:
        Excel parser -> Document AI with GENERAL context.

    SOAP:
        XML/WSDL/XSD -> SOAP parser -> Document AI with SAP_SOAP context.
        JSON         -> JSON parser -> Document AI with SAP_SOAP context.
        Excel        -> Excel parser -> Document AI with SAP_SOAP context.
    """
    extension = get_file_extension(uploaded_file)

    # ---------------------------------
    # General JSON
    # ---------------------------------
    if interface_type == "JSON":
        fields = flatten_json(
            read_json_file(uploaded_file)
        )

        return {
            "interface_id": "",
            "interface_name": "",
            "fields": normalize_standard_fields(fields),
        }

    # ---------------------------------
    # General File -> Excel
    # ---------------------------------
    if interface_type == "File":
        if extension in [".xlsx", ".xlsm"]:
            sheets = read_excel_file(uploaded_file)
            payload = build_excel_ai_payload(sheets)

            result = analyze_document_payload(
                document_payload=payload,
                role=role,
                file_name=uploaded_file.name,
            )

            result["fields"] = normalize_standard_fields(
                result.get("fields", [])
            )

            return result

        if extension == ".xls":
            raise ValueError(
                "Legacy .xls parsing is not implemented yet. "
                "Please use .xlsx or .xlsm for the current test."
            )

        raise ValueError(
            f"{extension} File parsing is not implemented yet. "
            "Current File flow supports .xlsx and .xlsm."
        )

    # ---------------------------------
    # SAP SOAP semantic context
    # ---------------------------------
    if interface_type == "SOAP":
        interface_context = "SAP_SOAP"

        # Real SOAP XML / WSDL / XSD
        if extension in [".xml", ".wsdl", ".xsd"]:
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
                interface_context=interface_context,
            )

            result["fields"] = normalize_standard_fields(
                result.get("fields", [])
            )

            return result

        # SOAP interface represented as JSON
        if extension == ".json":
            parsed_json = read_json_file(
                uploaded_file
            )

            parsed_fields = normalize_standard_fields(
                flatten_json(parsed_json)
            )

            payload = {
                "document_type": "SAP_SOAP_JSON_REPRESENTATION",
                "note": (
                    "This JSON represents or documents an SAP SOAP "
                    "interface. Preserve its field hierarchy and "
                    "interpret it using SAP SOAP semantics."
                ),
                "fields": parsed_fields,
            }

            result = analyze_document_payload(
                document_payload=payload,
                role=role,
                file_name=uploaded_file.name,
                interface_context=interface_context,
            )

            ai_fields = normalize_standard_fields(
                result.get("fields", [])
            )

            # Keep the deterministic JSON parse as a safe fallback.
            result["fields"] = (
                ai_fields
                if ai_fields
                else parsed_fields
            )

            return result

        # SOAP field specification provided as Excel
        if extension in [".xlsx", ".xlsm"]:
            sheets = read_excel_file(uploaded_file)
            payload = build_excel_ai_payload(sheets)

            result = analyze_document_payload(
                document_payload=payload,
                role=role,
                file_name=uploaded_file.name,
                interface_context=interface_context,
            )

            result["fields"] = normalize_standard_fields(
                result.get("fields", [])
            )

            return result

        if extension == ".xls":
            raise ValueError(
                "Legacy .xls parsing is not implemented yet. "
                "For SOAP Excel documents, please use .xlsx or .xlsm."
            )

        raise ValueError(
            f"Unsupported SOAP upload format: {extension}. "
            "Current SOAP flow supports XML, WSDL, XSD, JSON, "
            "XLSX and XLSM."
        )

    raise ValueError(
        f"{interface_type} parsing is not implemented yet."
    )


def is_interface_ready(uploaded_file, interface_type):
    if uploaded_file is None:
        return False

    extension = get_file_extension(uploaded_file)

    if interface_type == "JSON":
        return True

    if interface_type == "File":
        return extension in [
            ".xlsx",
            ".xlsm",
        ]

    if interface_type == "SOAP":
        return extension in [
            ".xml",
            ".wsdl",
            ".xsd",
            ".json",
            ".xlsx",
            ".xlsm",
        ]

    return False


def build_mapping_context(interface_type, side):
    """
    Give the final mapping model protocol/business context in addition
    to the normalized field list.
    """
    if interface_type == "SOAP":
        return f"""
{side} INTERFACE CONTEXT:
- Treat this side as an SAP SOAP interface.
- Use XML/SOAP element hierarchy and full Path when available.
- Consider parent business objects when interpreting generic field names.
- Consider Request/Response semantics when supported by the input.
- Consider XSD type, namespace, minOccurs/maxOccurs and required/optional
  semantics only when they are explicitly present.
- Do not invent missing SOAP/WSDL/XSD metadata.
"""

    return ""


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
    "source_field",
    "source_type",
    "source_size",
    "source_description",
    "source_remark",
    "mapping",
    "mapping_status",
    "target_path",
    "target_system",
    "target_table",
    "target_pk",
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
                    "source_field": field.get("Field", ""),
                    "source_type": field.get("Type", ""),
                    "source_size": field.get("Size", ""),
                    "source_description": field.get(
                        "Description", ""
                    ),
                    "source_remark": "",
                    "mapping": "",
                    "mapping_status": "Pending",
                    "target_path": "",
                    "target_system": "",
                    "target_table": "",
                    "target_pk": "",
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
                "source_field": "",
                "source_type": "",
                "source_size": "",
                "source_description": "",
                "source_remark": "",
                "mapping": "",
                "mapping_status": "Pending",
                "target_path": "",
                "target_system": "",
                "target_table": "",
                "target_pk": "",
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
                "순번 / Seq.": item.get("source_seq", ""),
                "송신 테이블 / Source Table": item.get("source_table", ""),
                "송신 PK / Source PK": item.get("source_pk", ""),
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
    page_title="Interface Mapping Assistant",
    page_icon="🔗",
    layout="wide",
)

st.title("🔗 Interface Mapping Assistant")
st.caption(
    "AI-powered interface field mapping assistant"
)

interface_types = [
    "JSON",
    "File",
    "Swagger",
    "EDI",
    "Open API",
    "SOAP",
    "Other",
]

FILE_FORMAT_HINT = (
    "PDF (.pdf) · Word (.docx) · "
    "Excel (.xlsx, .xls, .xlsm) · "
    "Images (.png, .jpg, .jpeg, .webp, .bmp, .tif, .tiff)"
)

SOAP_FORMAT_HINT = (
    "SOAP XML (.xml) · WSDL (.wsdl) · XSD (.xsd) · "
    "JSON representation (.json) · "
    "SOAP field document (.xlsx, .xls, .xlsm)"
)


# =========================
# Upload area
# =========================
left, right = st.columns(2)

with left:
    st.subheader("Source Interface")

    source_interface_type = st.selectbox(
        "Interface Type",
        interface_types,
        key="source_interface_type",
        help=(
            "Choose File for PDF, Word, Excel, "
            "or common image formats."
        ),
    )

    if source_interface_type == "File":
        st.caption(
            f"📎 Supported formats: {FILE_FORMAT_HINT}"
        )
    elif source_interface_type == "SOAP":
        st.caption(
            f"📎 SAP SOAP formats: {SOAP_FORMAT_HINT}"
        )
        st.caption(
            "SOAP is treated as the interface context. "
            "The uploaded artifact may be XML, JSON, or Excel."
        )

    source_file = st.file_uploader(
        "Upload Source Interface",
        type=get_allowed_file_types(
            source_interface_type
        ),
        key="source_interface",
    )

with right:
    st.subheader("Target Interface")

    target_interface_type = st.selectbox(
        "Interface Type",
        interface_types,
        key="target_interface_type",
        help=(
            "Choose File for PDF, Word, Excel, "
            "or common image formats."
        ),
    )

    if target_interface_type == "File":
        st.caption(
            f"📎 Supported formats: {FILE_FORMAT_HINT}"
        )
    elif target_interface_type == "SOAP":
        st.caption(
            f"📎 SAP SOAP formats: {SOAP_FORMAT_HINT}"
        )
        st.caption(
            "SOAP is treated as the interface context. "
            "The uploaded artifact may be XML, JSON, or Excel."
        )

    target_file = st.file_uploader(
        "Upload Target Interface",
        type=get_allowed_file_types(
            target_interface_type
        ),
        key="target_interface",
    )


# =========================
# Preview / validation
# =========================
source_preview_fields = None
target_preview_fields = None

if source_file is not None:
    if source_interface_type == "JSON":
        try:
            source_preview_fields = (
                normalize_standard_fields(
                    flatten_json(
                        read_json_file(source_file)
                    )
                )
            )
        except Exception as e:
            st.error(
                f"Failed to read Source JSON: {e}"
            )

    elif source_interface_type == "File":
        extension = get_file_extension(
            source_file
        )

        if extension in [".xlsx", ".xlsm"]:
            st.info(
                "Source Excel is ready. "
                "Click Generate AI Analysis & Mapping "
                "to analyze it."
            )
        else:
            st.info(
                f"Source {extension} File parser "
                "is not available yet."
            )

    elif source_interface_type == "SOAP":
        extension = get_file_extension(
            source_file
        )

        if extension in [
            ".xml",
            ".wsdl",
            ".xsd",
            ".json",
            ".xlsx",
            ".xlsm",
        ]:
            st.info(
                f"Source SAP SOAP {extension} is ready. "
                "It will be analyzed with SAP SOAP context."
            )
        elif extension == ".xls":
            st.warning(
                "Legacy .xls is not supported yet. "
                "Please save it as .xlsx."
            )
        else:
            st.info(
                f"Source SOAP format {extension} "
                "is not available yet."
            )

    else:
        st.info(
            f"Source {source_interface_type} parser "
            "is not available yet."
        )


if target_file is not None:
    if target_interface_type == "JSON":
        try:
            target_preview_fields = (
                normalize_standard_fields(
                    flatten_json(
                        read_json_file(target_file)
                    )
                )
            )
        except Exception as e:
            st.error(
                f"Failed to read Target JSON: {e}"
            )

    elif target_interface_type == "File":
        extension = get_file_extension(
            target_file
        )

        if extension in [".xlsx", ".xlsm"]:
            st.info(
                "Target Excel is ready. "
                "Click Generate AI Analysis & Mapping "
                "to analyze it."
            )
        else:
            st.info(
                f"Target {extension} File parser "
                "is not available yet."
            )

    elif target_interface_type == "SOAP":
        extension = get_file_extension(
            target_file
        )

        if extension in [
            ".xml",
            ".wsdl",
            ".xsd",
            ".json",
            ".xlsx",
            ".xlsm",
        ]:
            st.info(
                f"Target SAP SOAP {extension} is ready. "
                "It will be analyzed with SAP SOAP context."
            )
        elif extension == ".xls":
            st.warning(
                "Legacy .xls is not supported yet. "
                "Please save it as .xlsx."
            )
        else:
            st.info(
                f"Target SOAP format {extension} "
                "is not available yet."
            )

    else:
        st.info(
            f"Target {target_interface_type} parser "
            "is not available yet."
        )


# =========================
# Clear stale results when files change
# =========================
signature_parts = [
    source_interface_type,
    target_interface_type,
]

for uploaded in [
    source_file,
    target_file,
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

signature = "|".join(
    signature_parts
)

if (
    st.session_state.get(
        "file_signature"
    )
    != signature
):
    st.session_state["file_signature"] = signature

    reset_data(
        source_preview_fields
    )

if (
    "interface_info_df"
    not in st.session_state
):
    reset_data(
        source_preview_fields
    )


# =========================
# AI Analysis readiness
# =========================
source_ready = is_interface_ready(
    source_file,
    source_interface_type,
)

target_ready = is_interface_ready(
    target_file,
    target_interface_type,
)


# =========================
# AI Analysis
# =========================
if source_ready and target_ready:
    st.divider()

    if st.button(
        "Generate AI Analysis & Mapping",
        type="primary",
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
                source_result = analyze_uploaded_interface(
                    uploaded_file=source_file,
                    interface_type=source_interface_type,
                    role="source",
                )

            with st.spinner(
                "Preparing Target interface..."
            ):
                target_result = analyze_uploaded_interface(
                    uploaded_file=target_file,
                    interface_type=target_interface_type,
                    role="target",
                )

        except Exception as e:
            st.error(
                f"Interface parsing failed: {e}"
            )
            st.stop()

        source_fields = source_result["fields"]
        target_fields = target_result["fields"]

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
        # File mode: populate Interface ID / Name when available
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
        # Step 2: AI Mapping
        # =========================
        client = Anthropic(
            api_key=api_key,
            default_headers={
                "anthropic-workspace-id":
                    workspace_id
            },
        )

        source_mapping_context = build_mapping_context(
            source_interface_type,
            "SOURCE",
        )

        target_mapping_context = build_mapping_context(
            target_interface_type,
            "TARGET",
        )

        prompt = f"""
You are an enterprise interface mapping specialist.

The Source and Target fields below have already been normalized
from JSON or interface documents such as Excel.

Analyze ONLY:

1. Mapping Specification
2. Return Value

IMPORTANT GENERAL RULES:
- Never invent unsupported information.
- Unknown information must be returned as "".
- Do not force a mapping.
- Analyze every Source field.
- Always use full Path + Field together.
- Duplicate Field names may exist under different Paths.
- If no reliable Target exists, return target_path="" and target_field="".
- If no explicit return/response fields exist, return return_values=[].

SOURCE FILE:
{source_file.name}

SOURCE TYPE:
{source_interface_type}

TARGET FILE:
{target_file.name}

TARGET TYPE:
{target_interface_type}

{source_mapping_context}

{target_mapping_context}

SOURCE FIELDS:
{json.dumps(
    source_fields,
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
- source_path must exactly match an existing Source Path.
- source_field must match the Field belonging to source_path.
- Return one mapping item for every Source field.
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
"""

        with st.spinner(
            "Claude is mapping Source and Target fields..."
        ):
            ai = None
            last_error = None

            # Structured JSON can occasionally be returned incomplete.
            # Retry once with a larger output budget before failing.
            for attempt in range(2):
                try:
                    response = client.messages.parse(
                        model=model_name,
                        max_tokens=16000,
                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                        output_format=MappingAnalysisResult,
                    )

                    ai = response.parsed_output
                    break

                except Exception as e:
                    last_error = e

            if ai is None:
                st.error(
                    "Claude Mapping API call failed after retry: "
                    f"{last_error}"
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
