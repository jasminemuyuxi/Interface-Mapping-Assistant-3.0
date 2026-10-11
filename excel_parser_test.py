from pathlib import Path

from parsers.excel_parser import parse_excel_reference


FILE_PATH = Path(
    r"C:\Users\jasmi\Desktop\IF Mapping Test\JSON+Excel\TEST001 Outbound\TEST001 Target Outbound.xlsx"
)


with open(FILE_PATH, "rb") as f:
    result = parse_excel_reference(f)


print("Status:", result.get("status"))
print("Fields:", len(result.get("fields", [])))
print("Needs AI:", result.get("needs_ai"))
print("Warnings:", result.get("warnings"))
print()

print("Parsed Sheets:")
for sheet in result.get("parsed_sheets", []):
    print("-", sheet)

print()
print("First 10 Fields:")

for field in result.get("fields", [])[:10]:
    print(
        field.get("Field"),
        "|",
        field.get("Path"),
        "|",
        field.get("Type"),
        "|",
        field.get("Size"),
        "|",
        field.get("Description"),
    )