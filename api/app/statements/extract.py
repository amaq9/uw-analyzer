"""Finds candidate financial-statement figures in an uploaded file, for a person to check.

Nothing here is trusted: it suggests figures by matching line labels such as "Total current
liabilities" and reading the numbers on the same line. The person sees every suggestion next to its
label, corrects it, and only then confirms it (P-01, P-02: no figure enters the analysis unseen).
Supported: PDF with selectable text, Excel (.xlsx), CSV, Word (.docx) and plain text. Scanned images
and pictures cannot be read."""

import csv
import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from xml.etree import ElementTree

MAX_PDF_PAGES = 80
MAX_LINES = 6000

# metric -> (display label, regex on the normalised line label). Order matters: first match wins.
METRIC_LABELS: dict[str, str] = {
    "total_assets": "Total assets",
    "total_equity": "Total equity (shareholders' equity)",
    "current_assets": "Total current assets",
    "current_liabilities": "Total current liabilities",
    "cash": "Cash and cash equivalents",
    "short_term_investments": "Short-term investments / marketable securities",
    "receivables": "Accounts receivable, net",
    "allowance_for_credit_losses": "Allowance for credit losses",
    "inventory": "Inventories",
    "payables": "Accounts payable (trade payables)",
    "goodwill": "Goodwill",
    "intangibles": "Intangible assets, net",
    "debt_noncurrent": "Long-term debt (non-current)",
    "debt_current": "Current portion of long-term debt",
    "short_term_borrowings": "Short-term borrowings / notes payable",
    "lease_noncurrent": "Operating lease liabilities (non-current)",
    "lease_current": "Operating lease liabilities (current)",
    "revenue": "Revenue (net sales)",
    "gross_profit": "Gross profit",
    "cost_of_revenue": "Cost of sales (cost of goods sold)",
    "net_income": "Net income",
    "operating_income": "Operating income",
    "pretax_income": "Income before income taxes",
    "net_interest": "Net interest income (expense)",
    "interest_expense": "Interest expense",
    "depreciation_amortisation": "Depreciation and amortization",
    "ocf": "Net cash from operating activities",
    "capex": "Capital expenditure (purchase of property and equipment)",
    "dividends": "Dividends paid",
    "buybacks": "Share repurchases",
    "net_change_in_cash": "Net change in cash",
}

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("total_assets", re.compile(r"^total assets$")),
    ("current_assets", re.compile(r"^total current assets$")),
    ("current_liabilities", re.compile(r"^total current liabilities$")),
    (
        "total_equity",
        re.compile(
            r"^total (stockholders|shareholders|shareowners|owners)?'?s?'? ?(equity|deficit)( \(deficit\))?$|^total equity( \(deficit\))?$"
        ),
    ),
    (
        "short_term_investments",
        re.compile(
            r"^(short.?term investments|marketable securities|short.?term marketable securities)"
        ),
    ),
    (
        "cash",
        re.compile(
            r"^cash( and (cash )?equivalents)?( and restricted cash)?$|^cash and cash equivalents"
        ),
    ),
    (
        "allowance_for_credit_losses",
        re.compile(r"^(allowance for (doubtful accounts|credit losses|expected credit losses))"),
    ),
    ("receivables", re.compile(r"^(trade )?(accounts )?receivables?|^accounts receivable")),
    ("inventory", re.compile(r"^inventor(y|ies)")),
    ("payables", re.compile(r"^(trade )?(accounts )?payables?|^accounts payable")),
    (
        "cost_of_revenue",
        re.compile(
            r"^(total )?cost of (sales|revenues?|goods sold|products sold|goods and services sold)"
        ),
    ),
    ("goodwill", re.compile(r"^goodwill$")),
    ("intangibles", re.compile(r"^(other )?intangible assets|^intangibles")),
    (
        "debt_current",
        re.compile(
            r"^current (portion|maturities) of (long.?term )?(debt|borrowings|notes)|^current portion"
        ),
    ),
    (
        "short_term_borrowings",
        re.compile(
            r"^(short.?term (borrowings|debt|loans)|notes payable|commercial paper|bank (overdraft|loans))"
        ),
    ),
    (
        "debt_noncurrent",
        re.compile(
            r"^(long.?term (debt|borrowings|loans|notes)|notes payable, long.?term|senior notes)"
        ),
    ),
    (
        "lease_current",
        re.compile(
            r"^(current )?(portion of )?operating lease liabilit(y|ies),? current|^current operating lease"
        ),
    ),
    (
        "lease_noncurrent",
        re.compile(
            r"^operating lease liabilit(y|ies)( \(?non.?current\)?)?,? ?(non.?current)?$|^non.?current operating lease"
        ),
    ),
    ("gross_profit", re.compile(r"^gross (profit|margin)$")),
    (
        "net_interest",
        re.compile(
            r"^(interest (and other )?(income|expense),? net|net interest (income|expense))"
        ),
    ),
    ("interest_expense", re.compile(r"^interest expense|^finance (costs|expense)|^interest paid")),
    (
        "operating_income",
        re.compile(
            r"^(operating (income|profit|loss|earnings)|income from operations|profit from operations)"
        ),
    ),
    ("pretax_income", re.compile(r"^(income|earnings|profit) (\(loss\) )?before (income )?tax")),
    (
        "net_income",
        re.compile(
            r"^net (income|earnings|profit|loss)( \(loss\))?( attributable.*)?$|^(profit|loss) for the (year|period)"
        ),
    ),
    (
        "revenue",
        re.compile(
            r"^(total )?(net )?(revenues?|sales)( \(net\))?$|^total (net )?revenues?|^net sales|^turnover"
        ),
    ),
    (
        "depreciation_amortisation",
        re.compile(
            r"^depreciation( and|,|&) ?amortization|^depreciation and amortisation|^depreciation$"
        ),
    ),
    (
        "ocf",
        re.compile(
            r"^net cash (provided by|from|generated (by|from)|used in|\(used in\)|provided by \(used in\)|from \(used in\))[^a-z]*(operating|operations)|^cash flows? from operating activities$|^net cash (flows? )?(from|provided by) operating"
        ),
    ),
    (
        "capex",
        re.compile(
            r"^(purchases?|acquisitions?|additions?) (of|to) (property|plant|equipment|fixed assets|pp&e)|^capital expenditures?|^payments? (for|to acquire) (property|plant)"
        ),
    ),
    (
        "dividends",
        re.compile(r"^(cash )?dividends( paid)?|^dividends paid to (shareholders|stockholders)"),
    ),
    (
        "buybacks",
        re.compile(
            r"^(repurchases?|purchases?|payments? for repurchases?) of (common |treasury )?(stock|shares)|^share repurchases|^treasury stock purchases"
        ),
    ),
    (
        "net_change_in_cash",
        re.compile(
            r"^net (increase|decrease|change|\(decrease\) increase|increase \(decrease\)) in cash"
        ),
    ),
]

_NUMBER = re.compile(r"\(?-?[$€£]?\s?\d[\d,]*(?:\.\d+)?\)?%?|(?<=\s)[—–-](?=\s|$)")
_YEAR = re.compile(r"\b(?:19[9]\d|20\d\d|2100)\b")
_DATE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(20\d\d)",
    re.I,
)
_MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        1,
    )
}


@dataclass
class Row:
    metric: str
    label: str
    values: list[float | None]


@dataclass
class Extraction:
    period_labels: list[str] = field(default_factory=list)
    period_end_guesses: list[str | None] = field(default_factory=list)
    unit_guess: str | None = None
    currency_guess: str | None = None
    rows: list[Row] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class UnreadableFile(Exception):
    """The file type is not supported or its text could not be read."""


# --- turning files into lines of text -------------------------------------------------------


def _pdf_lines(data: bytes) -> list[str]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = reader.pages[:MAX_PDF_PAGES]
        text = "\n".join((page.extract_text() or "") for page in pages)
    except Exception:  # unreadable or damaged PDF
        raise UnreadableFile("The PDF could not be read.") from None
    return text.splitlines()


def _xlsx_lines(data: bytes) -> list[str]:
    from openpyxl import load_workbook

    try:
        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:
        raise UnreadableFile("The Excel file could not be read.") from None
    lines: list[str] = []
    for sheet in workbook.worksheets[:12]:
        for row in sheet.iter_rows(values_only=True):
            cells = [
                ""
                if c is None
                else (
                    f"{c:,}" if isinstance(c, int | float) and not isinstance(c, bool) else str(c)
                )
                for c in row
            ]
            if any(cells):
                lines.append("   ".join(cells))
            if len(lines) > MAX_LINES:
                return lines
    return lines


def _csv_lines(data: bytes) -> list[str]:
    text = data.decode("utf-8-sig", errors="replace")
    try:
        return ["   ".join(row) for row in csv.reader(io.StringIO(text))]
    except csv.Error:
        raise UnreadableFile("The CSV file could not be read.") from None


def _docx_lines(data: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))  # noqa: S314 - scanned, size-limited upload
    except Exception:
        raise UnreadableFile("The Word file could not be read.") from None
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    lines = []
    for para in root.iter(f"{{{ns['w']}}}tr"):
        cells = [
            "".join(t.text or "" for t in cell.iter(f"{{{ns['w']}}}t"))
            for cell in para.iter(f"{{{ns['w']}}}tc")
        ]
        lines.append("   ".join(cells))
    for para in root.iter(f"{{{ns['w']}}}p"):
        text = "".join(t.text or "" for t in para.iter(f"{{{ns['w']}}}t"))
        if text.strip():
            lines.append(text)
    return lines


def lines_of(filename: str, content_type: str, data: bytes) -> list[str]:
    name = filename.lower()
    if name.endswith(".pdf") or content_type == "application/pdf":
        return _pdf_lines(data)
    if name.endswith(".xlsx"):
        return _xlsx_lines(data)
    if name.endswith(".csv") or content_type == "text/csv":
        return _csv_lines(data)
    if name.endswith(".docx"):
        return _docx_lines(data)
    if name.endswith(".txt") or content_type.startswith("text/"):
        return data.decode("utf-8", errors="replace").splitlines()
    raise UnreadableFile(
        "This file type cannot be read for figures. Use a PDF with selectable text, Excel, CSV or Word."
    )


# --- reading a line ---------------------------------------------------------------------------


def _number(token: str) -> float | None:
    token = token.strip()
    if token in {"—", "–", "-"}:
        return 0.0
    negative = token.startswith("(") and token.endswith(")") or token.startswith("-")
    digits = re.sub(r"[^\d.]", "", token)
    if not digits or digits.count(".") > 1:
        return None
    value = float(digits)
    return -value if negative else value


def _split(line: str) -> tuple[str, list[float | None]]:
    """The label before the first number, and the numbers on the line."""
    line = line.replace(" ", " ").replace("−", "-")
    matches = list(_NUMBER.finditer(line))
    tokens = [m for m in matches if not m.group().endswith("%")]
    if not tokens:
        return line.strip(), []
    first = tokens[0]
    label = line[: first.start()].strip(" .:$\t")
    values = [_number(m.group()) for m in tokens]
    # drop a leading footnote marker such as "(1)" that is part of the label
    if len(values) > 1 and re.fullmatch(r"\(\d\)", tokens[0].group()):
        values = values[1:]
    return label, values


def _normal(label: str) -> str:
    label = re.sub(r"\(\d\)|\*+", "", label.lower())
    label = re.sub(r"[^a-z0-9()&' ,-]", " ", label)
    return re.sub(r"\s+", " ", label).strip(" ,:-")


def _headers(lines: list[str]) -> tuple[list[str], list[str | None]]:
    for line in lines[:80]:
        years = _YEAR.findall(line)
        if len(set(years)) >= 2 and len(line) < 200:
            ordered = list(dict.fromkeys(years))
            guesses: list[str | None] = []
            dates = [
                (m.group(1).lower(), int(m.group(2)), int(m.group(3))) for m in _DATE.finditer(line)
            ]
            by_year = {y: (m, d) for m, d, y in dates}
            for year in ordered:
                if int(year) in by_year:
                    month, day = by_year[int(year)]
                    guesses.append(date(int(year), _MONTHS[month], day).isoformat())
                else:
                    guesses.append(f"{year}-12-31")
            return ordered, guesses
    return [], []


def _unit(text: str) -> str | None:
    lowered = text.lower()
    if re.search(
        r"in millions|\(millions\)|millions of|\$ ?in millions|usd millions|\bmm\b", lowered
    ):
        return "millions"
    if re.search(r"in thousands|\(thousands\)|thousands of|\(000s?\)|\$000|'000", lowered):
        return "thousands"
    return None


def _currency(text: str) -> str | None:
    for code in ("USD", "CAD", "EUR", "GBP", "AUD", "CHF", "JPY"):
        if re.search(rf"\b{code}\b", text):
            return code
    if "C$" in text or "CAD" in text:
        return "CAD"
    if "€" in text:
        return "EUR"
    if "£" in text:
        return "GBP"
    if "$" in text:
        return "USD"
    return None


def extract(filename: str, content_type: str, data: bytes) -> Extraction:
    lines = [ln for ln in lines_of(filename, content_type, data)[:MAX_LINES] if ln.strip()]
    if not lines:
        raise UnreadableFile(
            "No text was found. A scanned picture cannot be read; use a PDF with selectable text."
        )
    text = "\n".join(lines)
    labels, guesses = _headers(lines)
    out = Extraction(
        period_labels=labels,
        period_end_guesses=guesses,
        unit_guess=_unit(text),
        currency_guess=_currency(text),
    )
    columns = len(labels) or 0
    seen: set[str] = set()
    for line in lines:
        label, values = _split(line)
        if not values or not label:
            continue
        key = _normal(label)
        for metric, pattern in _PATTERNS:
            if metric in seen or not pattern.search(key):
                continue
            usable = values[: columns or 3]
            if len(usable) < 1:
                continue
            seen.add(metric)
            out.rows.append(Row(metric=metric, label=label, values=usable))
            break
    width = max((len(r.values) for r in out.rows), default=0)
    if not out.period_labels and width:
        out.period_labels = [f"Column {i + 1}" for i in range(width)]
        out.period_end_guesses = [None] * width
        out.notes.append(
            "The period headings were not found. Enter each period's end date yourself."
        )
    for row in out.rows:
        row.values += [None] * (len(out.period_labels) - len(row.values))
    if out.unit_guess is None:
        out.notes.append(
            "The unit (units, thousands or millions) was not stated. Choose it before confirming."
        )
    if out.currency_guess is None:
        out.notes.append("The currency was not stated. Choose it before confirming.")
    for must in (
        "total_assets",
        "total_equity",
        "current_assets",
        "current_liabilities",
        "revenue",
        "ocf",
    ):
        if must not in seen:
            out.notes.append(
                f"Not found: {METRIC_LABELS[must].lower()}. Type it in if the document has it."
            )
    return out


def as_dict(extraction: Extraction) -> dict[str, Any]:
    return {
        "periods": extraction.period_labels,
        "rows": {r.metric: r.values for r in extraction.rows},
        "unit": extraction.unit_guess,
        "currency": extraction.currency_guess,
    }
