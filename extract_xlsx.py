import csv
import xml.etree.ElementTree as ET
import zipfile

XLSX_PATH = r"c:\Users\malle\.cursor\projects\finguard\legit payment datasets.xlsx"
OUT_PATH = r"c:\Users\malle\.cursor\projects\finguard\legit_payment_datasets.csv"

NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def col_to_num(col: str) -> int:
    total = 0
    for ch in col:
        total = total * 26 + (ord(ch) - 64)
    return total


with zipfile.ZipFile(XLSX_PATH) as zf:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}

    sheets = workbook.find("a:sheets", NS)
    first_sheet = sheets.findall("a:sheet", NS)[0]
    rid = first_sheet.attrib[
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    ]
    target = rel_map[rid]
    sheet_path = "xl/" + target if not target.startswith("xl/") else target

    shared = []
    try:
        sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in sst.findall("a:si", NS):
            text = "".join(t.text or "" for t in si.findall(".//a:t", NS))
            shared.append(text)
    except KeyError:
        pass

    sheet = ET.fromstring(zf.read(sheet_path))
    data = sheet.find("a:sheetData", NS)

rows = []
for row in data.findall("a:row", NS):
    vals = {}
    for cell in row.findall("a:c", NS):
        ref = cell.attrib.get("r", "A1")
        col = "".join(ch for ch in ref if ch.isalpha())
        cell_type = cell.attrib.get("t")
        v = cell.find("a:v", NS)
        value = ""
        if v is not None and v.text is not None:
            raw = v.text
            if cell_type == "s":
                idx = int(raw)
                value = shared[idx] if idx < len(shared) else ""
            else:
                value = raw
        vals[col] = value
    if vals:
        rows.append(vals)

columns = []
for r in rows:
    for k in r.keys():
        if k not in columns:
            columns.append(k)
columns = sorted(columns, key=col_to_num)

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(columns)
    for r in rows:
        writer.writerow([r.get(c, "") for c in columns])

print(
    f"WROTE {OUT_PATH} ROWS {len(rows)} COLS {len(columns)} SHEET {first_sheet.attrib.get('name','?')}"
)
