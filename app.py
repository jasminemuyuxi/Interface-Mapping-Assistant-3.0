import hashlib
import json
import os
from datetime import date

import pandas as pd
import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

from mapping.mapping_service import build_mapping_rows
from parsers.json_parser import flatten_json
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
# JSON mode:
# AI is currently used only for Mapping Specification
# and Return Value.
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
        "SOAP": ["xml", "wsdl", "xsd"],
        "Other": None,
    }.get(interface_type)


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

# Internal Mapping data model used by mapping_service.py + mapping_grid.py.
# Some fields (Path / Confidence / AI Reason) are intentionally kept hidden
# from the front-end grid for validation and future review features.
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
# Internal DataFrame keys remain unchanged for Sections 1, 2 and 4.
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
    return pd.DataFrame([row], columns=columns)


def build_interface_info_df():
    return one_row_df(
        INTERFACE_INFO_COLUMNS,
        {"생성일 / Creation Date": date.today().strftime("%Y.%m.%d")},
    )


def build_mapping_df(source_fields=None):
    """
    Initial Mapping grid before AI analysis.

    Parsed Source fields are shown as Pending.
    AI will later replace this DataFrame with the result from
    build_mapping_rows().
    """
    rows = []

    if source_fields:
        for seq, field in enumerate(source_fields, start=1):
            rows.append(
                {
                    "source_path": field.get("Path", ""),
                    "source_system": "",
                    "source_seq": seq,
                    "source_table": "",
                    "source_pk": "",
                    "source_field": field.get("Field", ""),
                    "source_type": field.get("Type", ""),
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

    return pd.DataFrame(rows, columns=MAPPING_GRID_COLUMNS)


def build_return_df():
    return one_row_df(
        RETURN_VALUE_COLUMNS,
        {
            "순번 / Seq.": 1,
            "Mapping / Mapping": "<-",
        },
    )


def reset_data(source_fields=None):
    st.session_state["interface_info_df"] = build_interface_info_df()
    st.session_state["source_transmission_df"] = one_row_df(
        SOURCE_TRANSMISSION_COLUMNS
    )
    st.session_state["target_transmission_df"] = one_row_df(
        TARGET_TRANSMISSION_COLUMNS
    )
    st.session_state["mapping_df"] = build_mapping_df(source_fields)
    st.session_state["return_value_df"] = build_return_df()
    st.session_state["editor_version"] = (
        st.session_state.get("editor_version", 0) + 1
    )


# =========================
# Mapping enrichment helpers
# =========================
def enrich_source_fields(source_fields, ai_mappings):
    ai_by_path = {
        item.source_path: item
        for item in ai_mappings
        if item.source_path
    }

    result = []

    for field in source_fields:
        item = ai_by_path.get(field.get("Path", ""))

        result.append(
            {
                "Path": field.get("Path", ""),
                "Field": field.get("Field", ""),
                "System": item.source_system if item else "",
                "PK": item.source_pk if item else "",
                "Type": (
                    item.source_type
                    if item and item.source_type
                    else field.get("Type", "")
                ),
                "Size": item.source_size if item else "",
                "Description": (
                    item.source_description if item else ""
                ),
            }
        )

    return result


def enrich_target_fields(target_fields, ai_mappings):
    ai_by_path = {}

    # The same Target may be referenced more than once.
    # Keep the first AI record containing useful Target metadata.
    for item in ai_mappings:
        if item.target_path and item.target_path not in ai_by_path:
            ai_by_path[item.target_path] = item

    result = []

    for field in target_fields:
        item = ai_by_path.get(field.get("Path", ""))

        result.append(
            {
                "Path": field.get("Path", ""),
                "Field": field.get("Field", ""),
                "System": item.target_system if item else "",
                "PK": item.target_pk if item else "",
                "Type": (
                    item.target_type
                    if item and item.target_type
                    else field.get("Type", "")
                ),
                "Size": item.target_size if item else "",
                "Description": (
                    item.target_description if item else ""
                ),
            }
        )

    return result


# =========================
# Page
# =========================
st.set_page_config(
    page_title="Interface Mapping Assistant",
    page_icon="🔗",
    layout="wide",
)

st.title("🔗 Interface Mapping Assistant")
st.caption("AI-powered interface field mapping assistant")

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
        help="Choose File for PDF, Word, Excel, or common image formats.",
    )

    if source_interface_type == "File":
        st.caption(f"📎 Supported formats: {FILE_FORMAT_HINT}")

    source_file = st.file_uploader(
        "Upload Source Interface",
        type=get_allowed_file_types(source_interface_type),
        key="source_interface",
    )

with right:
    st.subheader("Target Interface")

    target_interface_type = st.selectbox(
        "Interface Type",
        interface_types,
        key="target_interface_type",
        help="Choose File for PDF, Word, Excel, or common image formats.",
    )

    if target_interface_type == "File":
        st.caption(f"📎 Supported formats: {FILE_FORMAT_HINT}")

    target_file = st.file_uploader(
        "Upload Target Interface",
        type=get_allowed_file_types(target_interface_type),
        key="target_interface",
    )


# =========================
# Parse files
# =========================
source_fields = None
target_fields = None

if source_file is not None:
    if source_interface_type == "JSON":
        try:
            source_fields = flatten_json(read_json_file(source_file))
        except Exception as e:
            st.error(f"Failed to read Source JSON: {e}")
    else:
        st.info(
            f"Source {source_interface_type} parser is not available yet."
        )

if target_file is not None:
    if target_interface_type == "JSON":
        try:
            target_fields = flatten_json(read_json_file(target_file))
        except Exception as e:
            st.error(f"Failed to read Target JSON: {e}")
    else:
        st.info(
            f"Target {target_interface_type} parser is not available yet."
        )


# =========================
# Clear stale results when files change
# =========================
signature_parts = [source_interface_type, target_interface_type]

for uploaded in [source_file, target_file]:
    if uploaded is not None:
        signature_parts.extend(
            [
                uploaded.name,
                hashlib.sha256(uploaded.getvalue()).hexdigest(),
            ]
        )

signature = "|".join(signature_parts)

if st.session_state.get("file_signature") != signature:
    st.session_state["file_signature"] = signature
    reset_data(source_fields)

if "interface_info_df" not in st.session_state:
    reset_data(source_fields)


# =========================
# AI Analysis
# =========================
if source_fields is not None and target_fields is not None:
    st.divider()

    if st.button(
        "Generate AI Analysis & Mapping",
        type="primary",
    ):
        if not api_key:
            st.error("ANTHROPIC_API_KEY was not found.")
            st.stop()

        if not workspace_id:
            st.error("ANTHROPIC_WORKSPACE_ID was not found.")
            st.stop()

        client = Anthropic(
            api_key=api_key,
            default_headers={
                "anthropic-workspace-id": workspace_id
            },
        )

        prompt = f"""
You are an enterprise interface mapping specialist.

For this JSON-to-JSON analysis, analyze ONLY:

1. Mapping Specification
2. Return Value

Do NOT populate Interface Information or Transmission Information.
Those sections are maintained manually for JSON interfaces.

IMPORTANT GENERAL RULES:
- Never invent unsupported information.
- Unknown information must be returned as "".
- Do not force a mapping.
- Analyze every Source field.
- Always use full Path + Field together.
- Duplicate Field names may exist under different Paths.
- If no reliable Target exists, return target_path="" and target_field="".
- If no explicit return/response fields exist, return return_values=[].

SOURCE FILE: {source_file.name}
TARGET FILE: {target_file.name}

SOURCE FIELDS:
{json.dumps(source_fields, ensure_ascii=False, indent=2)}

TARGET FIELDS:
{json.dumps(target_fields, ensure_ascii=False, indent=2)}

MAPPING RULES:
- source_path must exactly match an existing Source Path.
- source_field must match the Field belonging to source_path.
- Return one mapping item for every Source field.
- target_path must exactly match an existing Target Path,
  or be "" when no reliable match exists.
- target_field must match the Field belonging to target_path,
  or be "" when no reliable match exists.

FIELD EXTRACTION RULES:
- source_system / target_system:
  extract only when supported by the input. Otherwise "".
- source_pk / target_pk:
  return "PK" only when the field can be identified as a primary key.
  Otherwise "".
- source_type / target_type:
  use explicit type information when available.
  For JSON, the parsed type may be used as the base type.
  If type is genuinely unknown, return "" rather than inventing one.
- source_size / target_size:
  fill only when supported by schema/document information.
  Do not treat the length of one sample value as the field's maximum size.
- source_description / target_description:
  fill only when supported by interface documentation or clear schema context.
  Otherwise "".
- Table is a manual-entry field and must not be inferred by AI.
- Remark is a manual-entry field and must not be inferred by AI.
- confidence must be 0-100.
- reason must briefly explain the mapping judgment.
"""

        with st.spinner("Claude is analyzing the interfaces..."):
            try:
                response = client.messages.parse(
                    model=model_name,
                    max_tokens=8000,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    output_format=MappingAnalysisResult,
                )
                ai = response.parsed_output
            except Exception as e:
                st.error(f"Claude API call failed: {e}")
                st.stop()

        # =========================
        # 3. Mapping Specification
        # =========================
        enriched_source_fields = enrich_source_fields(
            source_fields,
            ai.mappings,
        )
        enriched_target_fields = enrich_target_fields(
            target_fields,
            ai.mappings,
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

        st.session_state["mapping_df"] = pd.DataFrame(
            mapping_rows,
            columns=MAPPING_GRID_COLUMNS,
        )

        # =========================
        # 4. Return Value
        # =========================
        if ai.return_values:
            return_rows = []

            for seq, item in enumerate(ai.return_values, start=1):
                return_rows.append(
                    {
                        "송신 시스템 / Source System":
                            item.source_system,
                        "순번 / Seq.": seq,
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
                        "Mapping / Mapping": "<-",
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

            st.session_state["return_value_df"] = pd.DataFrame(
                return_rows,
                columns=RETURN_VALUE_COLUMNS,
            )
        else:
            st.session_state["return_value_df"] = build_return_df()

        # Force editors / grid to refresh with AI-filled values
        st.session_state["editor_version"] += 1
        st.rerun()


# =========================
# Four front-end sections
# =========================
version = st.session_state["editor_version"]


# 1. Interface Information
st.header("1. Interface Information")

edited = st.data_editor(
    st.session_state["interface_info_df"],
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config=make_text_column_config(INTERFACE_INFO_UI_LABELS),
    key=f"interface_info_editor_{version}",
)
st.session_state["interface_info_df"] = edited


# 2. Transmission Information
st.header("2. Transmission Information")

left, right = st.columns(2)

with left:
    st.subheader("Source Side")
    edited = st.data_editor(
        st.session_state["source_transmission_df"],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config=make_text_column_config(
            SOURCE_TRANSMISSION_UI_LABELS
        ),
        key=f"source_transmission_editor_{version}",
    )
    st.session_state["source_transmission_df"] = edited

with right:
    st.subheader("Target Side")
    edited = st.data_editor(
        st.session_state["target_transmission_df"],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config=make_text_column_config(
            TARGET_TRANSMISSION_UI_LABELS
        ),
        key=f"target_transmission_editor_{version}",
    )
    st.session_state["target_transmission_df"] = edited


# 3. Mapping Specification
st.header("3. Mapping Specification")
st.caption(
    "Edit the mapping if needed. "
    "Status is generated automatically from the mapping result."
)

edited_mapping_df = render_mapping_grid(
    st.session_state["mapping_df"],
    height=420,
    key=f"mapping_grid_{version}",
)

st.session_state["mapping_df"] = edited_mapping_df


# 4. Return Value
st.header("4. Return Value")

edited = st.data_editor(
    st.session_state["return_value_df"],
    use_container_width=True,
    hide_index=True,
    num_rows="dynamic",
    column_config={
        **make_text_column_config(RETURN_VALUE_UI_LABELS),
        "순번 / Seq.": st.column_config.NumberColumn("Seq."),
    },
    key=f"return_value_editor_{version}",
)

st.session_state["return_value_df"] = edited
