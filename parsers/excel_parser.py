from io import BytesIO

import openpyxl


def read_excel_file(uploaded_file):
    """
    Read an uploaded Excel file and return raw sheet content.

    Supported:
    - .xlsx
    - .xlsm

    Output format:
    [
        {
            "sheet_name": "Sheet1",
            "rows": [
                ["Field Name", "Type", "Size", "Description"],
                ["ORDER_NO", "VARCHAR", "20", "Order Number"],
                ...
            ]
        },
        ...
    ]
    """

    file_bytes = uploaded_file.getvalue()

    workbook = openpyxl.load_workbook(
        BytesIO(file_bytes),
        data_only=True,
        read_only=True,
    )

    sheets = []

    for worksheet in workbook.worksheets:
        rows = []

        for row in worksheet.iter_rows(values_only=True):
            cleaned_row = []

            for value in row:
                if value is None:
                    cleaned_row.append("")
                else:
                    cleaned_row.append(str(value).strip())

            # Skip fully empty rows
            if any(cell != "" for cell in cleaned_row):
                rows.append(cleaned_row)

        sheets.append(
            {
                "sheet_name": worksheet.title,
                "rows": rows,
            }
        )

    return sheets
from openpyxl.utils import get_column_letter


def build_excel_ai_payload(sheets):
    """
    Convert parsed Excel sheets into a compact structure
    that is easier for AI to understand.

    Empty cells are removed, while row/column positions
    are preserved.
    """

    result = []

    for sheet in sheets:
        ai_rows = []

        for row_index, row in enumerate(
            sheet["rows"],
            start=1,
        ):
            cells = []

            for column_index, value in enumerate(
                row,
                start=1,
            ):
                if value == "":
                    continue

                cell_address = (
                    f"{get_column_letter(column_index)}"
                    f"{row_index}"
                )

                cells.append(
                    {
                        "cell": cell_address,
                        "value": value,
                    }
                )

            if cells:
                ai_rows.append(
                    {
                        "row": row_index,
                        "cells": cells,
                    }
                )

        result.append(
            {
                "sheet_name": sheet["sheet_name"],
                "rows": ai_rows,
            }
        )

    return result