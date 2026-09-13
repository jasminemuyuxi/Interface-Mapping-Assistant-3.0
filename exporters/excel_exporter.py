from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins


# -----------------------------------------------------------------------------
# Visual theme - based on the company Mapping Specification screenshot
# -----------------------------------------------------------------------------
DARK_BLUE = "3F3F92"
PALE_YELLOW = "FFFDA3"
WHITE = "FFFFFF"
BLACK = "000000"
ARROW_BLUE = "2F55FF"
LIGHT_GRAY = "F2F2F2"

FONT_NAME = "맑은 고딕"

THIN_SIDE = Side(style="thin", color=BLACK)
MEDIUM_SIDE = Side(style="medium", color=BLACK)
THIN_BORDER = Border(
    left=THIN_SIDE,
    right=THIN_SIDE,
    top=THIN_SIDE,
    bottom=THIN_SIDE,
)


# Formal Excel columns. AI review-only columns are intentionally excluded.
SOURCE_EXPORT_COLUMNS = [
    "송신 시스템 / Source System",
    "순번 / Seq.",
    "송신 테이블 / Source Table",
    "송신 PK / Source PK",
    "송신 필드명 / Source Field",
    "송신 타입 / Source Type",
    "송신 사이즈 / Source Size",
    "송신 설명 / Source Description",
    "송신 비고 / Source Remark",
]

TARGET_EXPORT_COLUMNS = [
    "수신 시스템 / Target System",
    "수신 테이블 / Target Table",
    "수신 PK / Target PK",
    "최종 대상 필드 / Final Target Field",
    "수신 타입 / Target Type",
    "수신 사이즈 / Target Size",
    "수신 설명 / Target Description",
    "수신 비고 / Target Remark",
]

RETURN_SOURCE_COLUMNS = [
    "송신 시스템 / Source System",
    "순번 / Seq.",
    "송신 테이블 / Source Table",
    "송신 PK / Source PK",
    "송신 필드명 / Source Field",
    "송신 타입 / Source Type",
    "송신 사이즈 / Source Size",
    "송신 설명 / Source Description",
    "송신 비고 / Source Remark",
]

RETURN_TARGET_COLUMNS = [
    "수신 시스템 / Target System",
    "수신 테이블 / Target Table",
    "수신 PK / Target PK",
    "수신 필드명 / Target Field",
    "수신 타입 / Target Type",
    "수신 사이즈 / Target Size",
    "수신 설명 / Target Description",
    "수신 비고 / Target Remark",
]


# Display text for exported workbook languages.
# DataFrame column keys stay bilingual, so this only changes what users see in Excel.
LANGUAGE_TEXT = {
    "en": {
        "sheet_name": "Mapping Specification",
        "title": "INTERFACE DEFINITION [ Mapping Specification ]",
        "creation_date": "Creation Date",
        "author": "Author",
        "interface_information": "Interface Information",
        "interface_id": "Interface ID",
        "interface_name": "Interface Name",
        "interface_pattern": "Interface Pattern",
        "schedule_driven": "Schedule Driven",
        "execution_cycle": "Execution Cycle",
        "max_records": "Max Records",
        "average_records": "Average Records",
        "split_count": "Split Count",
        "transmission_information": "Transmission Information",
        "source_side": "Source Side",
        "target_side": "Target Side",
        "contact_name": "Contact Name",
        "department": "Department",
        "contact": "Contact",
        "integration_technology": "Integration Technology",
        "source_server": "Source Server",
        "target_server": "Target Server",
        "database": "DB",
        "adapter": "ADAPTER",
        "query_pattern": "Query Pattern",
        "processing_pattern": "Processing Pattern",
        "mapping_specification": "Mapping Specification",
        "mapping": "Mapping",
        "system": "System",
        "seq": "Seq.",
        "table": "Table",
        "pk": "PK",
        "field_name": "Field Name",
        "type": "Type",
        "size": "Size",
        "description": "Description",
        "remark": "Remark",
        "return_value": "Return Value",
    },
    "ko": {
        "sheet_name": "매핑 정의서",
        "title": "인터페이스 매핑 정의서",
        "creation_date": "생성일",
        "author": "작성자",
        "interface_information": "인터페이스 정보",
        "interface_id": "인터페이스 ID",
        "interface_name": "인터페이스 명",
        "interface_pattern": "인터페이스 패턴",
        "schedule_driven": "스케줄 구동",
        "execution_cycle": "실행 주기",
        "max_records": "최대 레코드(건)",
        "average_records": "평균 레코드(건)",
        "split_count": "분할 건수",
        "transmission_information": "전송 정보",
        "source_side": "송신측",
        "target_side": "수신측",
        "contact_name": "담당자 명",
        "department": "담당자 소속",
        "contact": "담당자 연락처",
        "integration_technology": "연계 기술",
        "source_server": "Source Svr",
        "target_server": "Target Svr",
        "database": "DB",
        "adapter": "ADAPTER",
        "query_pattern": "조회 패턴",
        "processing_pattern": "처리 패턴",
        "mapping_specification": "매핑 사양",
        "mapping": "Mapping",
        "system": "시스템",
        "seq": "순\n번",
        "table": "테이블",
        "pk": "PK",
        "field_name": "필드명",
        "type": "타입",
        "size": "사이\n즈",
        "description": "설명",
        "remark": "비고",
        "return_value": "반환값",
    },
}


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _clean(value: Any) -> Any:
    """Convert pandas/NumPy-ish empty values to Excel-safe blanks."""
    if value is None:
        return ""

    try:
        if value != value:  # NaN
            return ""
    except Exception:
        pass

    # Convert NumPy scalar-like objects to Python scalar if possible.
    try:
        if hasattr(value, "item"):
            return value.item()
    except Exception:
        pass

    return value


def _first_row(df: Any) -> dict[str, Any]:
    if df is None:
        return {}

    try:
        if df.empty:
            return {}
        return {k: _clean(v) for k, v in df.iloc[0].to_dict().items()}
    except Exception:
        return {}


def _records(df: Any) -> list[dict[str, Any]]:
    if df is None:
        return []

    try:
        if df.empty:
            return []
        return [
            {k: _clean(v) for k, v in row.items()}
            for row in df.to_dict(orient="records")
        ]
    except Exception:
        return []


def _set_value(ws, cell: str, value: Any, *, bold: bool = False,
               size: int = 10, color: str = BLACK,
               horizontal: str = "left", vertical: str = "center",
               wrap: bool = True):
    c = ws[cell]
    c.value = _clean(value)
    c.font = Font(name=FONT_NAME, size=size, bold=bold, color=color)
    c.alignment = Alignment(
        horizontal=horizontal,
        vertical=vertical,
        wrap_text=wrap,
    )
    return c


def _style_range(ws, cell_range: str, *, fill: str | None = None,
                 font_color: str = BLACK, bold: bool = False,
                 size: int = 10, horizontal: str = "center",
                 vertical: str = "center", wrap: bool = True,
                 border: Border | None = THIN_BORDER):
    for row in ws[cell_range]:
        for cell in row:
            if fill:
                cell.fill = PatternFill("solid", fgColor=fill)
            cell.font = Font(
                name=FONT_NAME,
                size=size,
                bold=bold,
                color=font_color,
            )
            cell.alignment = Alignment(
                horizontal=horizontal,
                vertical=vertical,
                wrap_text=wrap,
            )
            if border:
                cell.border = border


def _merge_label(ws, cell_range: str, text: str, *, fill: str = PALE_YELLOW,
                 size: int = 10, horizontal: str = "center"):
    ws.merge_cells(cell_range)
    start = cell_range.split(":")[0]
    _set_value(
        ws,
        start,
        text,
        bold=True,
        size=size,
        horizontal=horizontal,
    )
    _style_range(
        ws,
        cell_range,
        fill=fill,
        bold=True,
        size=size,
        horizontal=horizontal,
    )


def _merge_value(ws, cell_range: str, value: Any, *, horizontal: str = "left"):
    ws.merge_cells(cell_range)
    start = cell_range.split(":")[0]
    _set_value(ws, start, value, horizontal=horizontal)
    _style_range(
        ws,
        cell_range,
        fill=WHITE,
        bold=False,
        horizontal=horizontal,
    )


def _section_bar(ws, row: int, title: str):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=18)
    cell = ws.cell(row=row, column=1)
    cell.value = title
    cell.fill = PatternFill("solid", fgColor=DARK_BLUE)
    cell.font = Font(name=FONT_NAME, size=10, bold=True, color=WHITE)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    for col in range(1, 19):
        ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=DARK_BLUE)
        ws.cell(row=row, column=col).border = THIN_BORDER
    ws.row_dimensions[row].height = 20


def _merge_consecutive(ws, col: int, start_row: int, end_row: int):
    """Merge consecutive equal non-empty values in one column."""
    if end_row < start_row:
        return

    group_start = start_row
    previous = ws.cell(start_row, col).value

    for row in range(start_row + 1, end_row + 2):
        current = ws.cell(row, col).value if row <= end_row else object()
        if current != previous:
            if previous not in (None, "") and row - group_start > 1:
                ws.merge_cells(
                    start_row=group_start,
                    start_column=col,
                    end_row=row - 1,
                    end_column=col,
                )
                cell = ws.cell(group_start, col)
                cell.alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                    wrap_text=True,
                )
            group_start = row
            previous = current


def _apply_outer_border(ws, min_row: int, max_row: int,
                        min_col: int = 1, max_col: int = 18):
    """Slightly emphasize the outer border of the used business form."""
    for col in range(min_col, max_col + 1):
        top = ws.cell(min_row, col)
        bottom = ws.cell(max_row, col)
        top.border = Border(
            left=top.border.left,
            right=top.border.right,
            top=MEDIUM_SIDE,
            bottom=top.border.bottom,
        )
        bottom.border = Border(
            left=bottom.border.left,
            right=bottom.border.right,
            top=bottom.border.top,
            bottom=MEDIUM_SIDE,
        )

    for row in range(min_row, max_row + 1):
        left = ws.cell(row, min_col)
        right = ws.cell(row, max_col)
        left.border = Border(
            left=MEDIUM_SIDE,
            right=left.border.right,
            top=left.border.top,
            bottom=left.border.bottom,
        )
        right.border = Border(
            left=right.border.left,
            right=MEDIUM_SIDE,
            top=right.border.top,
            bottom=right.border.bottom,
        )


# -----------------------------------------------------------------------------
# Main export function
# -----------------------------------------------------------------------------
def create_interface_mapping_excel(
    interface_info_df,
    source_transmission_df,
    target_transmission_df,
    mapping_df,
    return_value_df,
    language: str = "en",
) -> bytes:
    """
    Build a company-style Interface Mapping Specification workbook.

    Parameters are the same DataFrames already stored in Streamlit session_state.
    The function returns raw .xlsx bytes so it can be passed directly to
    st.download_button(data=...).
    """

    if language not in LANGUAGE_TEXT:
        raise ValueError("language must be 'en' or 'ko'")

    text = LANGUAGE_TEXT[language]

    interface_info = _first_row(interface_info_df)
    source_tx = _first_row(source_transmission_df)
    target_tx = _first_row(target_transmission_df)
    mappings = _records(mapping_df)
    returns = _records(return_value_df)

    wb = Workbook()
    ws = wb.active
    ws.title = text["sheet_name"]
    ws.sheet_view.showGridLines = False

    # Column widths: A:R (18 columns)
    widths = {
        "A": 18, "B": 6, "C": 16, "D": 7, "E": 24, "F": 14,
        "G": 9, "H": 25, "I": 20, "J": 11,
        "K": 18, "L": 16, "M": 7, "N": 24, "O": 14,
        "P": 9, "Q": 25, "R": 20,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    # ------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------
    ws.merge_cells("A1:R1")
    _set_value(
        ws,
        "A1",
        text["title"],
        bold=True,
        size=18,
        horizontal="center",
    )
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 10

    # Blue separator like the screenshot
    ws.merge_cells("A3:R3")
    _style_range(ws, "A3:R3", fill=DARK_BLUE, border=THIN_BORDER)
    ws.row_dimensions[3].height = 11

    # ------------------------------------------------------------------
    # Basic creation info
    # ------------------------------------------------------------------
    _merge_label(ws, "A4:B4", text["creation_date"])
    _merge_value(
        ws,
        "C4:F4",
        interface_info.get("생성일 / Creation Date", ""),
        horizontal="center",
    )
    _merge_label(ws, "G4:H4", text["author"])
    _merge_value(
        ws,
        "I4:R4",
        interface_info.get("작성자 / Author", ""),
    )

    # ------------------------------------------------------------------
    # 1. Interface Information
    # ------------------------------------------------------------------
    _section_bar(ws, 5, text["interface_information"])

    _merge_label(ws, "A6:B6", text["interface_id"])
    _merge_value(ws, "C6:F6", interface_info.get("인터페이스 ID / Interface ID", ""))
    _merge_label(ws, "G6:H6", text["interface_name"])
    _merge_value(ws, "I6:R6", interface_info.get("인터페이스 명 / Interface Name", ""))

    _merge_label(ws, "A7:B7", text["interface_pattern"])
    _merge_value(ws, "C7:F7", interface_info.get("인터페이스 패턴 / Interface Pattern", ""))
    _merge_label(ws, "G7:H7", text["schedule_driven"])
    _merge_value(ws, "I7:L7", interface_info.get("스케줄 구동 / Schedule Driven", ""))
    _merge_label(ws, "M7:N7", text["execution_cycle"])
    _merge_value(ws, "O7:R7", interface_info.get("실행 주기 / Execution Cycle", ""))

    _merge_label(ws, "A8:B8", text["max_records"])
    _merge_value(ws, "C8:F8", interface_info.get("최대 레코드(건) / Max Records", ""))
    _merge_label(ws, "G8:H8", text["average_records"])
    _merge_value(ws, "I8:L8", interface_info.get("평균 레코드(건) / Average Records", ""))
    _merge_label(ws, "M8:N8", text["split_count"])
    _merge_value(ws, "O8:R8", interface_info.get("분할 건수 / Split Count", ""))

    # ------------------------------------------------------------------
    # 2. Transmission Information
    # ------------------------------------------------------------------
    _section_bar(ws, 9, text["transmission_information"])

    # Source side
    _merge_label(ws, "A10:A17", text["source_side"])
    _merge_label(ws, "B10:C10", text["contact_name"])
    _merge_value(ws, "D10:E10", source_tx.get("담당자 명 / Contact Name", ""))
    _merge_label(ws, "F10:G10", text["department"])
    _merge_value(ws, "H10:I10", source_tx.get("담당자 소속 / Department", ""))

    _merge_label(ws, "B11:C11", text["contact"])
    _merge_value(ws, "D11:I11", source_tx.get("담당자 연락처 / Contact", ""))
    _merge_label(ws, "B12:C12", text["integration_technology"])
    _merge_value(ws, "D12:I12", source_tx.get("연계 기술 / Integration Technology", ""))
    _merge_label(ws, "B13:C13", text["source_server"])
    _merge_value(ws, "D13:I13", source_tx.get("Source Svr / Source Server", ""))
    _merge_label(ws, "B14:C14", text["database"])
    _merge_value(ws, "D14:I14", source_tx.get("DB / Database", ""))
    _merge_label(ws, "B15:C15", text["adapter"])
    _merge_value(ws, "D15:I15", source_tx.get("ADAPTER / Adapter", ""))
    _merge_label(ws, "B16:C17", text["query_pattern"])
    _merge_value(ws, "D16:I17", source_tx.get("조회 패턴 / Query Pattern", ""))

    # Target side
    _merge_label(ws, "J10:J17", text["target_side"])
    _merge_label(ws, "K10:L10", text["contact_name"])
    _merge_value(ws, "M10:N10", target_tx.get("담당자 명 / Contact Name", ""))
    _merge_label(ws, "O10:P10", text["department"])
    _merge_value(ws, "Q10:R10", target_tx.get("담당자 소속 / Department", ""))

    _merge_label(ws, "K11:L11", text["contact"])
    _merge_value(ws, "M11:R11", target_tx.get("담당자 연락처 / Contact", ""))
    _merge_label(ws, "K12:L12", text["integration_technology"])
    _merge_value(ws, "M12:R12", target_tx.get("연계 기술 / Integration Technology", ""))
    _merge_label(ws, "K13:L13", text["target_server"])
    _merge_value(ws, "M13:R13", target_tx.get("Target Svr / Target Server", ""))
    _merge_label(ws, "K14:L14", text["database"])
    _merge_value(ws, "M14:R14", target_tx.get("DB / Database", ""))
    _merge_label(ws, "K15:L15", text["adapter"])
    _merge_value(ws, "M15:R15", target_tx.get("ADAPTER / Adapter", ""))
    _merge_label(ws, "K16:L17", text["processing_pattern"])
    _merge_value(ws, "M16:R17", target_tx.get("처리 패턴 / Processing Pattern", ""))

    for row in range(10, 18):
        ws.row_dimensions[row].height = 22
    ws.row_dimensions[16].height = 28
    ws.row_dimensions[17].height = 28

    # ------------------------------------------------------------------
    # 3. Mapping Specification
    # ------------------------------------------------------------------
    _section_bar(ws, 18, text["mapping_specification"])

    # Group headers
    ws.merge_cells("A19:I19")
    _set_value(ws, "A19", text["source_side"], bold=True, horizontal="center")
    _style_range(ws, "A19:I19", fill=PALE_YELLOW, bold=True)

    ws.merge_cells("J19:J20")
    _set_value(ws, "J19", text["mapping"], bold=True, horizontal="center")
    _style_range(ws, "J19:J20", fill=PALE_YELLOW, bold=True)

    ws.merge_cells("K19:R19")
    _set_value(ws, "K19", text["target_side"], bold=True, horizontal="center")
    _style_range(ws, "K19:R19", fill=PALE_YELLOW, bold=True)

    headers = [
        text["system"], text["seq"], text["table"], text["pk"],
        text["field_name"], text["type"], text["size"],
        text["description"], text["remark"],
        text["mapping"],
        text["system"], text["table"], text["pk"],
        text["field_name"], text["type"], text["size"],
        text["description"], text["remark"],
    ]

    # J20 belongs to merged J19:J20, so skip it.
    for col, header in enumerate(headers, start=1):
        if col == 10:
            continue
        cell = ws.cell(row=20, column=col)
        cell.value = header
        cell.fill = PatternFill("solid", fgColor=PALE_YELLOW)
        cell.font = Font(name=FONT_NAME, size=10, bold=True, color=BLACK)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = THIN_BORDER

    ws.row_dimensions[19].height = 25
    ws.row_dimensions[20].height = 38

    data_start_row = 21

    if not mappings:
        mappings = [{}]

    for offset, row_data in enumerate(mappings):
        r = data_start_row + offset

        source_values = [row_data.get(col, "") for col in SOURCE_EXPORT_COLUMNS]
        target_values = [row_data.get(col, "") for col in TARGET_EXPORT_COLUMNS]

        # Prefer human-final target field. If the page is still using the older
        # field name, gracefully fall back to it for preview/testing.
        if not target_values[3]:
            target_values[3] = row_data.get("수신 필드명 / Target Field", "")

        values = source_values + ["->"] + target_values

        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=r, column=col)
            cell.value = _clean(value)
            cell.border = THIN_BORDER
            cell.font = Font(
                name=FONT_NAME,
                size=9,
                color=ARROW_BLUE if col == 10 else BLACK,
            )
            cell.alignment = Alignment(
                horizontal="center" if col in (2, 4, 6, 7, 10, 13, 15, 16) else "left",
                vertical="center",
                wrap_text=True,
            )

        ws.row_dimensions[r].height = 20

    mapping_end_row = data_start_row + len(mappings) - 1

    # Merge repeated System cells to mimic the screenshot.
    _merge_consecutive(ws, 1, data_start_row, mapping_end_row)
    _merge_consecutive(ws, 11, data_start_row, mapping_end_row)

    # ------------------------------------------------------------------
    # 4. Return Value
    # ------------------------------------------------------------------
    return_title_row = mapping_end_row + 1
    ws.merge_cells(
        start_row=return_title_row,
        start_column=1,
        end_row=return_title_row,
        end_column=18,
    )
    _set_value(
        ws,
        f"A{return_title_row}",
        text["return_value"],
        bold=True,
        horizontal="left",
    )
    _style_range(
        ws,
        f"A{return_title_row}:R{return_title_row}",
        fill=PALE_YELLOW,
        bold=True,
        horizontal="left",
    )
    ws.row_dimensions[return_title_row].height = 20

    return_start_row = return_title_row + 1

    if not returns:
        returns = [{}]

    for offset, row_data in enumerate(returns):
        r = return_start_row + offset
        source_values = [row_data.get(col, "") for col in RETURN_SOURCE_COLUMNS]
        target_values = [row_data.get(col, "") for col in RETURN_TARGET_COLUMNS]
        values = source_values + ["<-"] + target_values

        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=r, column=col)
            cell.value = _clean(value)
            cell.border = THIN_BORDER
            cell.font = Font(
                name=FONT_NAME,
                size=9,
                color=ARROW_BLUE if col == 10 else BLACK,
            )
            cell.alignment = Alignment(
                horizontal="center" if col in (2, 4, 6, 7, 10, 13, 15, 16) else "left",
                vertical="center",
                wrap_text=True,
            )
        ws.row_dimensions[r].height = 20

    final_row = return_start_row + len(returns) - 1

    # ------------------------------------------------------------------
    # Print / page setup
    # ------------------------------------------------------------------
    ws.freeze_panes = None
    ws.print_area = f"A1:R{final_row}"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins = PageMargins(
        left=0.2,
        right=0.2,
        top=0.35,
        bottom=0.35,
        header=0.15,
        footer=0.15,
    )

    _apply_outer_border(ws, 3, final_row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()
