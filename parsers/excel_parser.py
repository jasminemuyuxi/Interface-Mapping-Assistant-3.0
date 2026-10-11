from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
from typing import Any, Callable, Iterable

import openpyxl
from openpyxl.utils import get_column_letter


# ============================================================
# Public design goals
# ============================================================
# 1. Deterministic parsing first.
# 2. Single-sheet and multi-sheet workbooks use the same pipeline.
# 3. One sheet may contain more than one field table.
# 4. Ambiguous / unknown blocks are returned for AI assistance.
# 5. Parsing problems degrade to PARTIAL/FAILED + warnings; the parser
#    should not crash the whole mapping workflow.
# 6. JSON/XML Structure remains authoritative elsewhere in the app.
#    This module only extracts Reference Document evidence.


# ============================================================
# Canonical header aliases
# ============================================================
HEADER_ALIASES = {
    "field": {
        # Chinese
        "参数名", "参数名称", "字段名", "字段名称", "属性名", "元素名", "节点名", "项目名",
        # English
        "field", "field name", "fieldname", "parameter", "parameter name", "parametername",
        "param", "param name", "attribute", "attribute name", "element", "element name",
        "property", "property name", "name",
        # Korean
        "필드", "필드명", "항목", "항목명", "파라미터", "파라미터명", "속성명", "요소명",
        # Japanese
        "項目", "項目名", "フィールド", "フィールド名", "パラメータ", "パラメータ名",
    },
    "path": {
        "参数路径", "字段路径", "属性路径", "元素路径", "节点路径", "完整路径",
        "path", "field path", "fieldpath", "parameter path", "parameterpath",
        "json path", "jsonpath", "xml path", "xmlpath", "xpath", "full path",
        "경로", "필드경로", "파라미터경로", "json경로", "xml경로",
        "パス", "項目パス", "フィールドパス",
    },
    "type": {
        "类型", "数据类型", "字段类型", "参数类型", "值类型",
        "type", "data type", "datatype", "field type", "parameter type", "value type",
        "타입", "유형", "데이터타입", "데이터유형", "필드타입",
        "型", "データ型", "タイプ",
    },
    "size": {
        "长度", "最大长度", "最小长度", "大小", "字节", "位数", "精度",
        "size", "length", "max length", "maxlength", "min length", "precision", "digits",
        "길이", "최대길이", "사이즈", "크기", "자리수",
        "長さ", "最大長", "桁数", "サイズ",
    },
    "sample": {
        "示例值", "示例", "样例", "样例值", "例子", "举例", "参考值",
        "example", "example value", "examplevalue", "sample", "sample value", "samplevalue",
        "예시", "예시값", "샘플", "샘플값", "예제", "예제값",
        "例", "例示", "サンプル", "サンプル値",
    },
    "description": {
        "说明", "描述", "字段说明", "参数说明", "字段描述", "参数描述", "业务说明", "业务含义",
        "备注", "含义", "定义", "用途",
        "description", "desc", "remark", "remarks", "meaning", "business meaning",
        "definition", "comment", "comments", "note", "notes", "usage",
        "설명", "필드설명", "항목설명", "파라미터설명", "비고", "의미", "정의",
        "説明", "備考", "意味", "定義",
    },
    "required": {
        "是否必填", "必填", "是否必须", "是否必需", "必选", "必须", "必需", "可选",
        "required", "mandatory", "required optional", "required/optional", "optional", "necessity",
        "필수", "필수여부", "필수 여부", "필수값", "필수옵션",
        "必須", "必須項目", "必須可否",
    },
    "level": {
        "层级", "层次", "级别", "节点层级", "depth", "level", "hierarchy level", "indent",
        "레벨", "단계", "계층", "계층레벨",
        "階層", "レベル",
    },
    "seq": {
        "序号", "顺序", "编号", "行号", "no", "no.", "number", "seq", "sequence", "index",
        "순번", "번호", "일련번호",
        "番号", "連番", "no",
    },
    "system": {
        "系统", "系统名", "系统名称", "来源系统", "目标系统",
        "system", "system name", "systemname", "source system", "target system",
        "시스템", "시스템명", "송신시스템", "수신시스템",
        "システム", "システム名",
    },
    "pk": {
        "pk", "primary key", "primarykey", "主键", "是否主键", "key", "키", "기본키", "主キー",
    },
}

INFO_KEY_ALIASES = {
    "interface_id": {
        "接口id", "接口编号", "接口编码", "接口code",
        "interface id", "interfaceid", "interface code", "interfacecode", "api id", "api code",
        "인터페이스id", "인터페이스번호", "인터페이스코드",
    },
    "interface_name": {
        "接口名称", "接口名", "api名称", "api名",
        "interface name", "interfacename", "api name",
        "인터페이스명", "api명",
    },
    "interface_description": {
        "接口说明", "接口描述", "api说明", "api描述",
        "interface description", "api description",
        "인터페이스설명", "api설명",
    },
    "direction": {
        "调用方向", "传输方向", "方向", "direction", "flow", "integration direction",
        "호출방향", "연계방향",
    },
}

SHEET_NAME_HINTS = {
    "metadata": {
        "接口信息", "基本信息", "概要", "说明", "interface info", "interface information",
        "basic info", "overview", "summary", "api info", "인터페이스정보", "기본정보",
    },
    "revision": {
        "修订记录", "变更记录", "版本记录", "revision", "revision history", "change log",
        "history", "version history", "변경이력", "개정이력",
    },
    "example": {
        "example", "examples", "sample", "samples", "示例", "样例", "예시", "샘플",
    },
    "code_table": {
        "code", "codes", "code table", "enum", "enumeration", "字典", "码表", "枚举",
        "코드", "코드표", "열거형",
    },
}

CODE_HEADER_ALIASES = {
    "code": {"code", "代码", "编码", "值", "value", "코드", "値"},
    "description": {"description", "meaning", "说明", "描述", "含义", "설명", "의미", "説明"},
}


# ============================================================
# Basic helpers
# ============================================================
def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _normalize_label(value: Any) -> str:
    text = _clean(value).lower()
    text = text.replace("／", "/")
    text = re.sub(r"[\s_\-:/\\（）()\[\]{}<>·•.,;；，。]+", "", text)
    return text


def _normalized_aliases(values: Iterable[str]) -> set[str]:
    return {_normalize_label(value) for value in values}


NORMALIZED_HEADER_ALIASES = {
    key: _normalized_aliases(values)
    for key, values in HEADER_ALIASES.items()
}

NORMALIZED_INFO_KEY_ALIASES = {
    key: _normalized_aliases(values)
    for key, values in INFO_KEY_ALIASES.items()
}

NORMALIZED_SHEET_NAME_HINTS = {
    key: _normalized_aliases(values)
    for key, values in SHEET_NAME_HINTS.items()
}

NORMALIZED_CODE_HEADER_ALIASES = {
    key: _normalized_aliases(values)
    for key, values in CODE_HEADER_ALIASES.items()
}


def _safe_filename(uploaded_file: Any) -> str:
    return _clean(getattr(uploaded_file, "name", "")) or "uploaded.xlsx"


def _extension(uploaded_file: Any) -> str:
    return Path(_safe_filename(uploaded_file)).suffix.lower()


def _get_bytes(uploaded_file: Any) -> bytes:
    """Support Streamlit UploadedFile, BytesIO and raw bytes."""
    if uploaded_file is None:
        return b""
    if isinstance(uploaded_file, bytes):
        return uploaded_file
    if isinstance(uploaded_file, bytearray):
        return bytes(uploaded_file)
    if hasattr(uploaded_file, "getvalue"):
        return uploaded_file.getvalue()
    if hasattr(uploaded_file, "read"):
        current = None
        try:
            if hasattr(uploaded_file, "tell"):
                current = uploaded_file.tell()
            data = uploaded_file.read()
            if current is not None and hasattr(uploaded_file, "seek"):
                uploaded_file.seek(current)
            return data
        except Exception:
            return b""
    return b""


def _trim_row(row: list[str]) -> list[str]:
    result = list(row)
    while result and result[-1] == "":
        result.pop()
    return result


def _is_blank_row(row: list[str]) -> bool:
    return not any(_clean(cell) for cell in row)




def _detect_message_section(sheet_name: str) -> str:
    """Conservatively classify a sheet as REQUEST / RESPONSE / UNKNOWN."""
    text = _normalize_label(sheet_name)
    if not text:
        return "UNKNOWN"

    response_tokens = [
        "response", "responseparameter", "responseparameters",
        "result", "resultparameter", "resultparameters",
        "响应", "响应参数", "返回", "返回参数", "返回值",
        "응답", "응답파라미터", "결과", "결과값",
    ]
    request_tokens = [
        "request", "requestparameter", "requestparameters",
        "input", "inputparameter", "inputparameters",
        "请求", "请求参数", "入参", "입력", "요청", "요청파라미터",
    ]

    if any(_normalize_label(token) in text for token in response_tokens):
        return "RESPONSE"
    if any(_normalize_label(token) in text for token in request_tokens):
        return "REQUEST"
    return "UNKNOWN"


# ============================================================
# Workbook reader (backward-compatible public API)
# ============================================================
def read_excel_file(uploaded_file: Any) -> list[dict[str, Any]]:
    """
    Read .xlsx/.xlsm workbook into a simple sheet/row structure.

    Backward-compatible return format:
        [
            {"sheet_name": "Request", "rows": [[...], [...]]},
            ...
        ]

    This low-level function raises ValueError for unsupported legacy .xls.
    The higher-level `parse_excel_reference()` catches all exceptions and
    returns FAILED/PARTIAL safely instead of crashing the app.
    """
    extension = _extension(uploaded_file)
    if extension == ".xls":
        raise ValueError(
            "Legacy .xls is not supported by the current parser. "
            "Please convert it to .xlsx or .xlsm."
        )
    if extension not in {".xlsx", ".xlsm"}:
        raise ValueError(
            f"Unsupported Excel format: {extension or '(unknown)'}. "
            "Supported formats are .xlsx and .xlsm."
        )

    file_bytes = _get_bytes(uploaded_file)
    if not file_bytes:
        raise ValueError("The uploaded Excel file is empty or unreadable.")

    workbook = openpyxl.load_workbook(
        BytesIO(file_bytes),
        data_only=True,
        read_only=True,
        keep_links=False,
    )

    sheets: list[dict[str, Any]] = []

    for worksheet in workbook.worksheets:
        rows: list[list[str]] = []
        source_row_numbers: list[int] = []

        for excel_row_number, row in enumerate(
            worksheet.iter_rows(values_only=True),
            start=1,
        ):
            cleaned = _trim_row([_clean(value) for value in row])
            if _is_blank_row(cleaned):
                continue
            rows.append(cleaned)
            source_row_numbers.append(excel_row_number)

        sheets.append(
            {
                "sheet_name": worksheet.title,
                "rows": rows,
                # Preserve real Excel row numbers even when blank rows are removed.
                "source_row_numbers": source_row_numbers,
            }
        )

    return sheets


# ============================================================
# AI payload builder (backward-compatible public API)
# ============================================================
def build_excel_ai_payload(sheets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert sheets into a cell-address-aware payload for AI."""
    result: list[dict[str, Any]] = []

    for sheet in sheets or []:
        ai_rows = []
        rows = sheet.get("rows", []) or []
        source_row_numbers = sheet.get("source_row_numbers", []) or []

        for compact_index, row in enumerate(rows):
            excel_row = (
                source_row_numbers[compact_index]
                if compact_index < len(source_row_numbers)
                else compact_index + 1
            )
            cells = []
            for column_index, value in enumerate(row, start=1):
                if _clean(value) == "":
                    continue
                cells.append(
                    {
                        "cell": f"{get_column_letter(column_index)}{excel_row}",
                        "value": _clean(value),
                    }
                )
            if cells:
                ai_rows.append({"row": excel_row, "cells": cells})

        result.append(
            {
                "sheet_name": sheet.get("sheet_name", ""),
                "rows": ai_rows,
            }
        )

    return result


# ============================================================
# Header detection
# ============================================================
def _match_header_name(cell_value: Any) -> tuple[str | None, int]:
    """
    Return (canonical_header, confidence).

    Confidence:
      100 = exact normalized alias match
       85 = cautious containment match
        0 = no match
    """
    normalized = _normalize_label(cell_value)
    if not normalized:
        return None, 0

    # Exact aliases first.
    for canonical, aliases in NORMALIZED_HEADER_ALIASES.items():
        if normalized in aliases:
            return canonical, 100

    # Conservative containment. Only use longer labels to avoid matching
    # generic words such as "name" or "type" too aggressively.
    if len(normalized) >= 5:
        candidates: list[tuple[str, int]] = []
        for canonical, aliases in NORMALIZED_HEADER_ALIASES.items():
            for alias in aliases:
                if len(alias) < 4:
                    continue
                if alias in normalized or normalized in alias:
                    candidates.append((canonical, 85))
                    break
        if len({name for name, _ in candidates}) == 1:
            return candidates[0]

    return None, 0


def _analyze_header_row(row: list[str]) -> dict[str, Any]:
    column_map: dict[str, int] = {}
    header_confidence: dict[str, int] = {}
    unknown_columns: list[dict[str, Any]] = []

    for column_index, value in enumerate(row):
        canonical, confidence = _match_header_name(value)
        if canonical and canonical not in column_map:
            column_map[canonical] = column_index
            header_confidence[canonical] = confidence
        elif _clean(value):
            unknown_columns.append(
                {
                    "column_index": column_index,
                    "header": _clean(value),
                }
            )

    # Field is the strongest evidence. Path/description/type/sample etc.
    # increase confidence that this is really an interface field table.
    score = 0
    if "field" in column_map:
        score += 45
    if "path" in column_map:
        score += 20
    if "description" in column_map:
        score += 15
    if "type" in column_map:
        score += 10
    if "sample" in column_map:
        score += 5
    if "required" in column_map:
        score += 5
    if "level" in column_map:
        score += 5
    if "seq" in column_map:
        score += 3
    if "size" in column_map:
        score += 3

    exact_ratio = 1.0
    if header_confidence:
        exact_ratio = sum(header_confidence.values()) / (100 * len(header_confidence))
    score = int(round(score * exact_ratio))

    return {
        "score": score,
        "column_map": column_map,
        "header_confidence": header_confidence,
        "unknown_columns": unknown_columns,
    }


def _find_header_candidates(rows: list[list[str]], min_score: int = 55) -> list[dict[str, Any]]:
    candidates = []
    for compact_row_index, row in enumerate(rows):
        analysis = _analyze_header_row(row)
        if analysis["score"] >= min_score and "field" in analysis["column_map"]:
            analysis = dict(analysis)
            analysis["compact_row_index"] = compact_row_index
            candidates.append(analysis)
    return candidates


# ============================================================
# Sheet classification
# ============================================================
def _sheet_name_matches(sheet_name: str, category: str) -> bool:
    normalized = _normalize_label(sheet_name)
    if not normalized:
        return False
    for alias in NORMALIZED_SHEET_NAME_HINTS.get(category, set()):
        if normalized == alias or alias in normalized:
            return True
    return False


def _looks_like_key_value_metadata(rows: list[list[str]]) -> bool:
    if not rows:
        return False
    sample = rows[:20]
    two_col_like = sum(1 for row in sample if 2 <= len(row) <= 3)
    if two_col_like / max(len(sample), 1) < 0.6:
        return False

    known_keys = 0
    for row in sample:
        if not row:
            continue
        key = _normalize_label(row[0])
        for aliases in NORMALIZED_INFO_KEY_ALIASES.values():
            if key in aliases:
                known_keys += 1
                break
    return known_keys >= 1 or two_col_like >= 4


def _looks_like_code_table(rows: list[list[str]]) -> bool:
    for row in rows[:12]:
        normalized_cells = [_normalize_label(v) for v in row]
        code_hit = any(v in NORMALIZED_CODE_HEADER_ALIASES["code"] for v in normalized_cells)
        desc_hit = any(v in NORMALIZED_CODE_HEADER_ALIASES["description"] for v in normalized_cells)
        if code_hit and desc_hit:
            return True
    return False


def classify_sheet(sheet: dict[str, Any]) -> str:
    rows = sheet.get("rows", []) or []
    sheet_name = _clean(sheet.get("sheet_name", ""))

    if not rows:
        return "EMPTY"

    candidates = _find_header_candidates(rows)
    if candidates:
        return "FIELD_DEFINITION"

    if _sheet_name_matches(sheet_name, "revision"):
        return "REVISION_HISTORY"
    if _sheet_name_matches(sheet_name, "metadata") or _looks_like_key_value_metadata(rows):
        return "METADATA"
    if _sheet_name_matches(sheet_name, "code_table") or _looks_like_code_table(rows):
        return "CODE_TABLE"
    if _sheet_name_matches(sheet_name, "example"):
        return "EXAMPLE"

    return "UNKNOWN"


# ============================================================
# Field extraction helpers
# ============================================================
def _row_value(row: list[str], column_map: dict[str, int], key: str) -> str:
    index = column_map.get(key)
    if index is None or index >= len(row):
        return ""
    return _clean(row[index])


def _parse_type_and_size(type_value: Any, explicit_size: Any = "") -> tuple[str, str]:
    raw_type = _clean(type_value)
    raw_size = _clean(explicit_size)
    if not raw_type:
        return "", raw_size

    # String(50), Decimal(18,3), VARCHAR2(100 BYTE)
    match = re.match(r"^\s*([^()]+?)\s*\(\s*([^()]+?)\s*\)\s*$", raw_type)
    if match:
        return match.group(1).strip(), raw_size or match.group(2).strip()

    # Some documents use String[50]
    match = re.match(r"^\s*([^\[\]]+?)\s*\[\s*([^\[\]]+?)\s*\]\s*$", raw_type)
    if match:
        return match.group(1).strip(), raw_size or match.group(2).strip()

    return raw_type, raw_size


def _normalize_pk(value: Any) -> str:
    normalized = _normalize_label(value)
    positives = {
        "pk", "primarykey", "key", "y", "yes", "true", "1", "是", "主键",
        "키", "기본키", "主キー",
    }
    return "PK" if normalized in positives else ""


def _safe_int(value: Any) -> int | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def _reconstruct_path_from_level(
    field_name: str,
    level_value: Any,
    path_stack: dict[int, str],
) -> str:
    level = _safe_int(level_value)
    if not field_name:
        return ""
    if level is None or level <= 1:
        if level is not None:
            path_stack[level] = field_name
            for key in list(path_stack):
                if key > level:
                    path_stack.pop(key, None)
        return field_name

    parent_parts = []
    for parent_level in range(1, level):
        if parent_level in path_stack:
            parent_parts.append(path_stack[parent_level])

    path_stack[level] = field_name
    for key in list(path_stack):
        if key > level:
            path_stack.pop(key, None)

    if parent_parts:
        return ".".join(parent_parts + [field_name])
    return field_name


def _is_probable_repeated_header(row: list[str], original_header: list[str]) -> bool:
    if not row or not original_header:
        return False
    a = [_normalize_label(x) for x in row]
    b = [_normalize_label(x) for x in original_header]
    if a == b:
        return True
    analysis = _analyze_header_row(row)
    return analysis["score"] >= 55 and "field" in analysis["column_map"]


def _extract_table(
    *,
    sheet: dict[str, Any],
    header_candidate: dict[str, Any],
    table_index: int,
    end_compact_row_index: int,
    reference_file_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = sheet.get("rows", []) or []
    source_row_numbers = sheet.get("source_row_numbers", []) or []
    header_index = header_candidate["compact_row_index"]
    column_map = header_candidate["column_map"]
    header_row = rows[header_index]
    sheet_name = _clean(sheet.get("sheet_name", ""))

    fields: list[dict[str, Any]] = []
    warnings: list[str] = []
    path_stack: dict[int, str] = {}
    blank_like_count = 0

    for compact_index in range(header_index + 1, end_compact_row_index):
        row = rows[compact_index]
        if _is_probable_repeated_header(row, header_row):
            continue

        field_name = _row_value(row, column_map, "field")
        raw_path = _row_value(row, column_map, "path")
        level = _row_value(row, column_map, "level")

        # Ignore non-field explanatory rows inside a table.
        if not field_name:
            blank_like_count += 1
            if blank_like_count >= 3:
                # Do not hard-stop if the next rows could still be fields; the
                # table boundary is determined by next detected header.
                pass
            continue
        blank_like_count = 0

        raw_type = _row_value(row, column_map, "type")
        explicit_size = _row_value(row, column_map, "size")
        data_type, size = _parse_type_and_size(raw_type, explicit_size)

        if raw_path:
            path = raw_path
            # Keep hierarchy stack synchronized if a level exists.
            level_int = _safe_int(level)
            if level_int is not None:
                path_stack[level_int] = field_name
                for key in list(path_stack):
                    if key > level_int:
                        path_stack.pop(key, None)
        else:
            path = _reconstruct_path_from_level(field_name, level, path_stack)

        excel_row = (
            source_row_numbers[compact_index]
            if compact_index < len(source_row_numbers)
            else compact_index + 1
        )

        extraction_confidence = min(
            100,
            int(header_candidate["score"] + (10 if raw_path else 0)),
        )

        issues = []
        if not raw_path:
            issues.append("Path was not explicitly documented; parser reconstructed/fell back to Field.")
        if not data_type:
            issues.append("Type is not documented.")

        fields.append(
            {
                "Path": path or field_name,
                "Field": field_name,
                "System": _row_value(row, column_map, "system"),
                "PK": _normalize_pk(_row_value(row, column_map, "pk")),
                "Type": data_type,
                "Size": size,
                "Description": _row_value(row, column_map, "description"),
                "Sample": _row_value(row, column_map, "sample"),
                "Required": _row_value(row, column_map, "required"),
                "Level": level,
                "Seq": _row_value(row, column_map, "seq"),
                # Provenance / reliability evidence
                "Reference File": reference_file_name,
                "Reference Sheet": sheet_name,
                "Reference Row": excel_row,
                "Reference Table": table_index,
                "Sheet Category": "FIELD_DEFINITION",
                "Message Section": _detect_message_section(sheet_name),
                "Field Origin": "REFERENCE_ONLY",
                "Extraction Method": "deterministic",
                "Extraction Confidence": extraction_confidence,
                "Extraction Issues": issues,
            }
        )

    if not fields:
        warnings.append(
            f"No field rows were extracted from sheet '{sheet_name}', table {table_index}."
        )

    table_meta = {
        "sheet_name": sheet_name,
        "table_index": table_index,
        "status": "PARSED" if fields else "EMPTY",
        "header_row": (
            source_row_numbers[header_index]
            if header_index < len(source_row_numbers)
            else header_index + 1
        ),
        "field_count": len(fields),
        "score": header_candidate["score"],
        "columns": sorted(column_map.keys()),
        "unknown_columns": header_candidate["unknown_columns"],
        "warnings": warnings,
    }
    return fields, table_meta


# ============================================================
# Metadata / support extraction
# ============================================================
def _extract_interface_info(sheets: list[dict[str, Any]]) -> dict[str, str]:
    info = {
        "interface_id": "",
        "interface_name": "",
        "interface_description": "",
        "direction": "",
    }

    for sheet in sheets or []:
        rows = sheet.get("rows", []) or []
        for row in rows:
            if len(row) < 2:
                continue
            key = _normalize_label(row[0])
            value = _clean(row[1])
            if not key or not value:
                continue
            for canonical, aliases in NORMALIZED_INFO_KEY_ALIASES.items():
                if not info[canonical] and key in aliases:
                    info[canonical] = value
                    break

    return info


def _supporting_sheet_payload(sheet: dict[str, Any], category: str) -> dict[str, Any]:
    return {
        "sheet_name": _clean(sheet.get("sheet_name", "")),
        "category": category,
        "rows": sheet.get("rows", []) or [],
        "source_row_numbers": sheet.get("source_row_numbers", []) or [],
    }


# ============================================================
# Deterministic workbook parser
# ============================================================
def extract_interface_fields_from_excel(
    sheets: list[dict[str, Any]],
    *,
    reference_file_name: str = "",
) -> dict[str, Any]:
    """
    Parse all sheets in one workbook.

    Safe return schema:
        {
            "status": "success" | "partial" | "failed",
            "interface_id": str,
            "interface_name": str,
            "interface_description": str,
            "direction": str,
            "fields": list[dict],
            "parsed_sheets": list[dict],
            "supporting_sheets": list[dict],
            "unresolved_blocks": list[dict],
            "warnings": list[str],
            "needs_ai": bool,
        }
    """
    info = _extract_interface_info(sheets)
    fields: list[dict[str, Any]] = []
    parsed_sheets: list[dict[str, Any]] = []
    supporting_sheets: list[dict[str, Any]] = []
    unresolved_blocks: list[dict[str, Any]] = []
    warnings: list[str] = []

    for sheet in sheets or []:
        sheet_name = _clean(sheet.get("sheet_name", ""))
        rows = sheet.get("rows", []) or []
        category = classify_sheet(sheet)

        if category == "EMPTY":
            parsed_sheets.append(
                {
                    "sheet_name": sheet_name,
                    "category": category,
                    "status": "IGNORED",
                    "field_count": 0,
                }
            )
            continue

        if category == "FIELD_DEFINITION":
            candidates = _find_header_candidates(rows)
            # Handle more than one field table in a single sheet.
            for table_pos, candidate in enumerate(candidates, start=1):
                next_header_index = (
                    candidates[table_pos]["compact_row_index"]
                    if table_pos < len(candidates)
                    else len(rows)
                )
                table_fields, table_meta = _extract_table(
                    sheet=sheet,
                    header_candidate=candidate,
                    table_index=table_pos,
                    end_compact_row_index=next_header_index,
                    reference_file_name=reference_file_name,
                )
                fields.extend(table_fields)
                parsed_sheets.append(table_meta)

                # If header recognition was not exact or many columns remain
                # unexplained, keep a small AI-review block without blocking
                # deterministic results.
                low_header_confidence = any(
                    confidence < 100
                    for confidence in candidate["header_confidence"].values()
                )
                if low_header_confidence:
                    unresolved_blocks.append(
                        {
                            "reference_file": reference_file_name,
                            "sheet_name": sheet_name,
                            "reason": "Header aliases were matched approximately.",
                            "block_type": "AMBIGUOUS_HEADER",
                            "header_row": table_meta.get("header_row"),
                            "rows": rows[
                                candidate["compact_row_index"]:
                                min(next_header_index, candidate["compact_row_index"] + 30)
                            ],
                        }
                    )
            continue

        # Known non-field sheets remain available as reference context but do
        # not create fields and do not automatically require AI.
        if category in {
            "METADATA",
            "REVISION_HISTORY",
            "CODE_TABLE",
            "EXAMPLE",
        }:
            supporting_sheets.append(_supporting_sheet_payload(sheet, category))
            parsed_sheets.append(
                {
                    "sheet_name": sheet_name,
                    "category": category,
                    "status": "SUPPORTING_REFERENCE",
                    "field_count": 0,
                }
            )
            continue

        # Unknown non-empty sheet: preserve it and ask AI later.
        unresolved_blocks.append(
            {
                "reference_file": reference_file_name,
                "sheet_name": sheet_name,
                "reason": "Non-empty sheet could not be classified deterministically.",
                "block_type": "UNKNOWN_SHEET",
                "rows": rows,
            }
        )
        parsed_sheets.append(
            {
                "sheet_name": sheet_name,
                "category": "UNKNOWN",
                "status": "NEEDS_AI",
                "field_count": 0,
            }
        )

    # No field table at all: AI should inspect non-empty sheets, including
    # supporting sheets, because some customers may encode fields in an
    # unconventional format that resembles metadata or examples.
    if not fields:
        existing_names = {b.get("sheet_name") for b in unresolved_blocks}
        for sheet in sheets or []:
            if not (sheet.get("rows") or []):
                continue
            name = _clean(sheet.get("sheet_name", ""))
            if name in existing_names:
                continue
            unresolved_blocks.append(
                {
                    "reference_file": reference_file_name,
                    "sheet_name": name,
                    "reason": "No deterministic field table was found in the workbook.",
                    "block_type": "FALLBACK_WORKBOOK_SCAN",
                    "rows": sheet.get("rows", []) or [],
                }
            )

    # Remove exact duplicate fields created by accidental duplicate table
    # detection, but never collapse same-named fields from different paths or
    # sheets.
    deduped_fields: list[dict[str, Any]] = []
    seen = set()
    for field in fields:
        key = (
            _clean(field.get("Reference File")),
            _clean(field.get("Reference Sheet")),
            _clean(field.get("Path")),
            _clean(field.get("Field")),
            _clean(field.get("Reference Row")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped_fields.append(field)
    fields = deduped_fields

    if fields and unresolved_blocks:
        status = "partial"
    elif fields:
        status = "success"
    else:
        status = "failed"
        warnings.append("No interface fields were extracted deterministically.")

    if unresolved_blocks:
        warnings.append(
            f"{len(unresolved_blocks)} Excel block(s) need AI-assisted interpretation."
        )

    return {
        "status": status,
        **info,
        "fields": fields,
        "parsed_sheets": parsed_sheets,
        "supporting_sheets": supporting_sheets,
        "unresolved_blocks": unresolved_blocks,
        "warnings": warnings,
        "needs_ai": bool(unresolved_blocks),
    }


# ============================================================
# AI-assistance payload and conservative merge
# ============================================================
def build_unresolved_ai_payload(parse_result: dict[str, Any]) -> dict[str, Any]:
    """
    Build a compact payload ONLY for unresolved/ambiguous Excel content.

    The AI should identify structure/semantics for these blocks. It should not
    re-interpret or overwrite deterministic fields that were already parsed.
    """
    blocks = []
    for block in parse_result.get("unresolved_blocks", []) or []:
        rows_payload = []
        for row_index, row in enumerate(block.get("rows", []) or [], start=1):
            cells = [
                {"column": index + 1, "value": _clean(value)}
                for index, value in enumerate(row)
                if _clean(value)
            ]
            if cells:
                rows_payload.append({"row": row_index, "cells": cells})

        blocks.append(
            {
                "reference_file": block.get("reference_file", ""),
                "sheet_name": block.get("sheet_name", ""),
                "reason": block.get("reason", ""),
                "block_type": block.get("block_type", ""),
                "rows": rows_payload,
            }
        )

    return {
        "instruction": (
            "Interpret only the unresolved Excel blocks. Extract interface "
            "field definitions when supported by the document. Do not invent "
            "fields. Do not overwrite deterministic parser results."
        ),
        "blocks": blocks,
    }


def merge_ai_assisted_fields(
    parse_result: dict[str, Any],
    ai_fields: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    Add AI-extracted fields conservatively.

    AI is allowed to add evidence from unresolved blocks, but it does NOT
    overwrite an existing deterministic field with the same file/sheet/path.
    """
    result = dict(parse_result or {})
    deterministic_fields = list(result.get("fields", []) or [])
    warnings = list(result.get("warnings", []) or [])

    if not ai_fields:
        return result

    existing_keys = {
        (
            _clean(field.get("Reference File")),
            _clean(field.get("Reference Sheet")),
            _clean(field.get("Path")),
            _clean(field.get("Field")),
        )
        for field in deterministic_fields
    }

    added = 0
    for raw in ai_fields:
        if not isinstance(raw, dict):
            continue

        field_name = _clean(
            raw.get("Field")
            or raw.get("field")
            or raw.get("Name")
            or raw.get("name")
        )
        if not field_name:
            continue

        path = _clean(raw.get("Path") or raw.get("path")) or field_name
        reference_file = _clean(
            raw.get("Reference File")
            or raw.get("reference_file")
        )
        reference_sheet = _clean(
            raw.get("Reference Sheet")
            or raw.get("reference_sheet")
            or raw.get("sheet_name")
        )

        key = (reference_file, reference_sheet, path, field_name)
        if key in existing_keys:
            continue

        data_type, size = _parse_type_and_size(
            raw.get("Type") or raw.get("type"),
            raw.get("Size") or raw.get("size"),
        )

        deterministic_fields.append(
            {
                "Path": path,
                "Field": field_name,
                "System": _clean(raw.get("System") or raw.get("system")),
                "PK": _normalize_pk(raw.get("PK") or raw.get("pk")),
                "Type": data_type,
                "Size": size,
                "Description": _clean(
                    raw.get("Description") or raw.get("description")
                ),
                "Sample": _clean(raw.get("Sample") or raw.get("sample")),
                "Required": _clean(raw.get("Required") or raw.get("required")),
                "Level": _clean(raw.get("Level") or raw.get("level")),
                "Seq": _clean(raw.get("Seq") or raw.get("seq")),
                "Reference File": reference_file,
                "Reference Sheet": reference_sheet,
                "Reference Row": _clean(
                    raw.get("Reference Row") or raw.get("reference_row")
                ),
                "Reference Table": _clean(
                    raw.get("Reference Table") or raw.get("reference_table")
                ),
                "Sheet Category": _clean(
                    raw.get("Sheet Category") or raw.get("sheet_category")
                ) or "AI_INTERPRETED",
                "Field Origin": "REFERENCE_ONLY",
                "Extraction Method": "ai_assisted",
                "Extraction Confidence": _safe_int(
                    raw.get("Extraction Confidence")
                    or raw.get("extraction_confidence")
                    or raw.get("confidence")
                ) or 60,
                "Extraction Issues": [
                    "Field was extracted from an Excel block that deterministic parsing could not resolve."
                ],
            }
        )
        existing_keys.add(key)
        added += 1

    result["fields"] = deterministic_fields
    if added:
        warnings.append(f"AI-assisted parsing added {added} field(s).")
        result["status"] = "success" if deterministic_fields else result.get("status", "partial")
    result["warnings"] = warnings
    return result


# ============================================================
# High-level safe entry point
# ============================================================
def parse_excel_reference(
    uploaded_file: Any,
    *,
    ai_assist: Callable[[dict[str, Any]], list[dict[str, Any]] | dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """
    Fault-tolerant Excel Reference parser.

    Optional `ai_assist` callback receives `build_unresolved_ai_payload()` and
    may return either:
        - list[dict]                         -> AI fields
        - {"fields": list[dict], ...}       -> AI fields + optional metadata

    IMPORTANT: any AI failure is converted to warnings; this function should
    still return a structured result instead of crashing the whole Mapping app.
    """
    file_name = _safe_filename(uploaded_file)

    base_failed = {
        "status": "failed",
        "interface_id": "",
        "interface_name": "",
        "interface_description": "",
        "direction": "",
        "fields": [],
        "parsed_sheets": [],
        "supporting_sheets": [],
        "unresolved_blocks": [],
        "warnings": [],
        "needs_ai": False,
        "reference_file": file_name,
    }

    try:
        sheets = read_excel_file(uploaded_file)
    except Exception as exc:
        result = dict(base_failed)
        result["warnings"] = [f"Excel read failed: {exc}"]
        # Legacy .xls or corrupted workbooks should fail safely, not crash.
        return result

    try:
        result = extract_interface_fields_from_excel(
            sheets,
            reference_file_name=file_name,
        )
        result["reference_file"] = file_name
    except Exception as exc:
        result = dict(base_failed)
        result["warnings"] = [f"Deterministic Excel parsing failed safely: {exc}"]
        result["needs_ai"] = True
        result["unresolved_blocks"] = [
            {
                "reference_file": file_name,
                "sheet_name": sheet.get("sheet_name", ""),
                "reason": "Deterministic parser raised an internal error; send to AI fallback.",
                "block_type": "PARSER_FALLBACK",
                "rows": sheet.get("rows", []) or [],
            }
            for sheet in sheets
            if sheet.get("rows")
        ]

    if not result.get("needs_ai") or ai_assist is None:
        return result

    try:
        payload = build_unresolved_ai_payload(result)
        ai_response = ai_assist(payload)

        if isinstance(ai_response, dict):
            ai_fields = ai_response.get("fields", []) or []
        elif isinstance(ai_response, list):
            ai_fields = ai_response
        else:
            ai_fields = []

        result = merge_ai_assisted_fields(result, ai_fields)
    except Exception as exc:
        warnings = list(result.get("warnings", []) or [])
        warnings.append(f"AI-assisted Excel interpretation failed safely: {exc}")
        result["warnings"] = warnings

    return result
