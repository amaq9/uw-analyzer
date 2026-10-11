"""Small generated financial-statement files for tests (no real company data)."""

import io
import zipfile

LINES = [
    "Acme Holdings Ltd",
    "Consolidated statements (in thousands of CAD)",
    "For the years ended December 31, 2025 and December 31, 2024    2025    2024",
    "Total current assets    24,600    23,300",
    "Total assets    38,400    36,500",
    "Cash and cash equivalents    7,563    7,464",
    "Accounts receivable, net    5,931    4,717",
    "Inventories    7,501    7,489",
    "Goodwill    240    240",
    "Total current liabilities    12,547    10,566",
    "Long-term debt    5,942    7,961",
    "Current portion of long-term debt    2,000    —",
    "Total shareholders' equity    14,865    13,213",
    "Revenues    46,398    46,309",
    "Net income    3,108    3,219",
    "Depreciation and amortization    747    775",
    "Net cash provided by operating activities    2,868    3,698",
    "Purchases of property and equipment    (684)    (430)",
    "Dividends paid    (2,407)    (2,300)",
    "Repurchase of common stock    (146)    (2,985)",
    "Net increase (decrease) in cash    99    (2,396)",
    "Interest expense (1)    323    389",
]

SECOND_YEAR_FIGURES = {
    "total_assets": 38400,
    "total_equity": 14865,
    "current_assets": 24600,
    "current_liabilities": 12547,
    "cash": 7563,
    "receivables": 5931,
    "inventory": 7501,
    "debt_noncurrent": 5942,
    "debt_current": 2000,
    "revenue": 46398,
    "net_income": 3108,
    "ocf": 2868,
    "capex": 684,
    "dividends": 2407,
    "buybacks": 146,
    "depreciation_amortisation": 747,
    "interest_expense": 323,
}


def text_bytes() -> bytes:
    return "\n".join(LINES).encode()


def csv_bytes() -> bytes:
    return "\n".join(",".join(f'"{c}"' for c in line.split("    ")) for line in LINES).encode()


def xlsx_bytes() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for line in LINES:
        parts = line.split("    ")
        row: list[object] = [parts[0]]
        for cell in parts[1:]:
            cleaned = cell.replace(",", "").replace("(", "-").replace(")", "")
            row.append(float(cleaned) if cleaned.lstrip("-").replace(".", "").isdigit() else cell)
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def docx_bytes() -> bytes:
    paragraphs = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in LINES)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paragraphs}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def pdf_bytes() -> bytes:
    """A minimal one-page PDF with selectable text, one line per statement line."""

    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream = (
        "BT /F1 9 Tf 40 780 Td 12 TL\n"
        + "\n".join(f"({escape(line.replace(chr(0x2014), chr(0x2D)))}) Tj T*" for line in LINES)
        + "\nET"
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 800] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out
