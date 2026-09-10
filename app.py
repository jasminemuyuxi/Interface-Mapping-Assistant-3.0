import json
import os

import pandas as pd
import streamlit as st

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel


# ==========================================
# 1. 读取环境变量
# ==========================================

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
model_name = os.getenv(
    "CLAUDE_MODEL",
    "claude-sonnet-5",
)


# ==========================================
# 2. Claude Mapping 数据结构
# ==========================================

class MappingItem(BaseModel):
    source_path: str
    source_field: str

    target_path: str
    target_field: str

    confidence: int
    reason: str


class MappingResult(BaseModel):
    mappings: list[MappingItem]


# ==========================================
# 3. JSON 字段解析函数
# ==========================================

def flatten_json(data, parent_path=""):
    fields = []

    if isinstance(data, dict):

        for key, value in data.items():

            if parent_path:
                path = f"{parent_path}.{key}"
            else:
                path = key

            # ------------------------------
            # 嵌套 Object
            # ------------------------------
            if isinstance(value, dict):

                fields.extend(
                    flatten_json(
                        value,
                        path,
                    )
                )

            # ------------------------------
            # Array
            # ------------------------------
            elif isinstance(value, list):

                if (
                    len(value) > 0
                    and isinstance(value[0], dict)
                ):

                    fields.extend(
                        flatten_json(
                            value[0],
                            path + "[]",
                        )
                    )

                else:

                    fields.append(
                        {
                            "Path": path,
                            "Field": key,
                            "Type": "array",
                            "Sample": str(value),
                        }
                    )

            # ------------------------------
            # 普通字段
            # ------------------------------
            else:

                fields.append(
                    {
                        "Path": path,
                        "Field": key,
                        "Type": type(value).__name__,
                        "Sample": (
                            ""
                            if value is None
                            else str(value)
                        ),
                    }
                )

    return fields


# ==========================================
# 4. 根据 Interface Type
#    决定允许上传的文件格式
# ==========================================

def get_allowed_file_types(interface_type):

    file_type_map = {
        "JSON": ["json"],
        "PDF": ["pdf"],
        "Swagger": ["json", "yaml", "yml"],
        "EDI": ["edi", "txt"],
        "Open API": ["json", "yaml", "yml"],
        "SOAP": ["xml", "wsdl", "xsd"],
        "Other": None,
    }

    return file_type_map.get(interface_type)


# ==========================================
# 5. Streamlit 页面设置
# ==========================================

st.set_page_config(
    page_title="Interface Mapping Assistant",
    page_icon="🔗",
    layout="wide",
)

st.title("🔗 Interface Mapping Assistant")

st.caption(
    "AI-powered interface field mapping assistant"
)


# ==========================================
# 6. Interface Type
# ==========================================

interface_types = [
    "JSON",
    "PDF",
    "Swagger",
    "EDI",
    "Open API",
    "SOAP",
    "Other",
]


# ==========================================
# 7. Source / Target Interface 上传
# ==========================================

col1, col2 = st.columns(2)


with col1:

    st.subheader(
        "Source Interface"
    )

    source_interface_type = st.selectbox(
        "Interface Type",
        interface_types,
        key="source_interface_type",
    )

    source_file = st.file_uploader(
        "Upload Source Interface",
        type=get_allowed_file_types(
            source_interface_type
        ),
        key="source_interface",
    )


with col2:

    st.subheader(
        "Target Interface"
    )

    target_interface_type = st.selectbox(
        "Interface Type",
        interface_types,
        key="target_interface_type",
    )

    target_file = st.file_uploader(
        "Upload Target Interface",
        type=get_allowed_file_types(
            target_interface_type
        ),
        key="target_interface",
    )


# ==========================================
# 8. Source / Target 初始化
# ==========================================

source_fields = None
target_fields = None


# ==========================================
# 9. Source Interface 解析
# ==========================================

if source_file is not None:

    if source_interface_type == "JSON":

        try:

            source_data = json.load(
                source_file
            )

            source_fields = flatten_json(
                source_data
            )

            st.subheader(
                "Source Interface Fields"
            )

            st.dataframe(
                source_fields,
                use_container_width=True,
            )

        except Exception as e:

            st.error(
                f"Source JSON 读取失败：{e}"
            )

    else:

        st.info(
            f"{source_interface_type} "
            "解析功能暂未开发，"
            "当前版本仅支持 JSON 字段解析。"
        )


# ==========================================
# 10. Target Interface 解析
# ==========================================

if target_file is not None:

    if target_interface_type == "JSON":

        try:

            target_data = json.load(
                target_file
            )

            target_fields = flatten_json(
                target_data
            )

            st.subheader(
                "Target Interface Fields"
            )

            st.dataframe(
                target_fields,
                use_container_width=True,
            )

        except Exception as e:

            st.error(
                f"Target JSON 读取失败：{e}"
            )

    else:

        st.info(
            f"{target_interface_type} "
            "解析功能暂未开发，"
            "当前版本仅支持 JSON 字段解析。"
        )


# ==========================================
# 11. Claude AI Mapping
# ==========================================

if (
    source_fields is not None
    and target_fields is not None
):

    st.divider()

    if st.button(
        "Generate AI Mapping",
        type="primary",
    ):

        # ------------------------------
        # 检查 API Key
        # ------------------------------

        if not api_key:

            st.error(
                "没有找到 ANTHROPIC_API_KEY，"
                "请检查 .env 文件。"
            )

            st.stop()


        # ------------------------------
        # 检查 Workspace ID
        # ------------------------------

        if not workspace_id:

            st.error(
                "没有找到 "
                "ANTHROPIC_WORKSPACE_ID，"
                "请检查 .env 文件。"
            )

            st.stop()


        # ------------------------------
        # 创建 Claude Client
        # ------------------------------

        client = Anthropic(
            api_key=api_key,
            default_headers={
                "anthropic-workspace-id":
                    workspace_id
            },
        )


        # ------------------------------
        # Claude Prompt
        # ------------------------------

        prompt = f"""
You are an interface field mapping specialist.

Your task is to map every Source Interface field
to the most appropriate Target Interface field.

IMPORTANT:

Each field has BOTH:

- Path
- Field

The Path represents the complete location
of the field inside the interface structure.

For example:

sender.name
receiver.name

Both fields may have the same Field name "name",
but they represent different business meanings.

Therefore:

You MUST use Path together with Field
when performing mapping.

Analyze:

1. Full field path
2. Field name
3. Data type
4. Sample value
5. Business meaning
6. Parent object meaning

Source Interface fields:

{json.dumps(
    source_fields,
    ensure_ascii=False,
    indent=2
)}

Target Interface fields:

{json.dumps(
    target_fields,
    ensure_ascii=False,
    indent=2
)}

Rules:

- Analyze every Source field.

- source_path must exactly match
  an existing Source Path.

- source_field must exactly match
  the Field associated with source_path.

- target_path must exactly match
  an existing Target Path.

- target_field must exactly match
  the Field associated with target_path.

- Do not invent fields or paths.

- Always consider the full path,
  especially when duplicate field names exist.

- confidence must be an integer
  from 0 to 100.

- Lower confidence when business meaning
  is uncertain.

- Give a short reason explaining
  why the Source and Target match.

Return the result using the required
structured output format.
"""


        # ------------------------------
        # 调用 Claude
        # ------------------------------

        with st.spinner(
            "Claude is analyzing "
            "the interface fields..."
        ):

            try:

                response = (
                    client.messages.parse(
                        model=model_name,
                        max_tokens=6000,
                        messages=[
                            {
                                "role": "user",
                                "content": prompt,
                            }
                        ],
                        output_format=(
                            MappingResult
                        ),
                    )
                )

                mapping_result = (
                    response.parsed_output
                )

            except Exception as e:

                st.error(
                    f"Claude API 调用失败：{e}"
                )

                st.stop()


        # ==================================
        # Claude结果转换为表格
        # ==================================

        mapping_rows = []

        for item in mapping_result.mappings:

            mapping_rows.append(
                {
                    "Source Path":
                        item.source_path,

                    "Source Field":
                        item.source_field,

                    "Target Path":
                        item.target_path,

                    "Target Field":
                        item.target_field,

                    "Confidence":
                        item.confidence,

                    "Reason":
                        item.reason,

                    "Review Status":
                        "Pending",

                    "Remark":
                        "",
                }
            )


        st.session_state[
            "mapping_df"
        ] = pd.DataFrame(
            mapping_rows
        )


# ==========================================
# 12. 可编辑 Mapping Table
# ==========================================

if "mapping_df" in st.session_state:

    st.subheader(
        "Mapping Result"
    )

    edited_df = st.data_editor(
        st.session_state[
            "mapping_df"
        ],
        use_container_width=True,
        hide_index=True,

        # Source 原始字段不能修改
        disabled=[
            "Source Path",
            "Source Field",
        ],

        column_config={

            "Confidence":
                st.column_config.NumberColumn(
                    "Confidence",
                    min_value=0,
                    max_value=100,
                ),

            "Review Status":
                st.column_config.SelectboxColumn(
                    "Review Status",
                    options=[
                        "Pending",
                        "Confirmed",
                        "Rejected",
                    ],
                ),
        },

        key="mapping_editor",
    )

    st.session_state[
        "mapping_df"
    ] = edited_df