"""Reading suggested figures out of uploaded files (pure, no database)."""

import pytest

from app.statements.extract import UnreadableFile, extract
from tests.statement_files import csv_bytes, docx_bytes, pdf_bytes, text_bytes, xlsx_bytes

FILES = {
    "statements.txt": ("text/plain", text_bytes),
    "statements.csv": ("text/csv", csv_bytes),
    "statements.xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        xlsx_bytes,
    ),
    "statements.docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx_bytes,
    ),
    "statements.pdf": ("application/pdf", pdf_bytes),
}


@pytest.mark.parametrize("name", list(FILES))
def test_every_supported_format_gives_the_same_suggestions(name: str) -> None:
    content_type, make = FILES[name]
    found = extract(name, content_type, make())
    rows = {r.metric: r for r in found.rows}
    assert found.period_labels == ["2025", "2024"]
    assert found.period_end_guesses == ["2025-12-31", "2024-12-31"]
    assert found.unit_guess == "thousands" and found.currency_guess == "CAD"
    assert rows["total_assets"].values == [38400.0, 36500.0]
    assert rows["current_liabilities"].values == [12547.0, 10566.0]
    assert rows["total_equity"].values == [14865.0, 13213.0]
    assert rows["revenue"].values == [46398.0, 46309.0]
    assert rows["ocf"].values == [2868.0, 3698.0]
    assert rows["receivables"].label.lower().startswith("accounts receivable")


def test_brackets_mean_negative_and_a_dash_means_nil() -> None:
    rows = {r.metric: r for r in extract("s.txt", "text/plain", text_bytes()).rows}
    assert rows["capex"].values == [-684.0, -430.0]
    assert rows["net_change_in_cash"].values == [99.0, -2396.0]
    assert rows["debt_current"].values == [2000.0, 0.0]


def test_a_footnote_marker_is_not_read_as_a_number() -> None:
    rows = {r.metric: r for r in extract("s.txt", "text/plain", text_bytes()).rows}
    assert rows["interest_expense"].values == [323.0, 389.0]


def test_missing_lines_are_reported_not_invented() -> None:
    found = extract("s.txt", "text/plain", text_bytes())
    metrics = {r.metric for r in found.rows}
    assert "gross_profit" not in metrics and "allowance_for_credit_losses" not in metrics
    assert not any("Not found: total assets" in n.lower() for n in found.notes)


def test_missing_unit_currency_and_headings_are_flagged() -> None:
    raw = b"Total assets 100 90\nTotal current assets 60 55\nTotal current liabilities 30 28\n"
    found = extract("s.txt", "text/plain", raw)
    assert found.unit_guess is None and found.currency_guess is None
    assert found.period_labels == ["Column 1", "Column 2"] and found.period_end_guesses == [
        None,
        None,
    ]
    assert any("unit" in n for n in found.notes) and any("currency" in n for n in found.notes)
    assert any("period headings" in n for n in found.notes)


def test_dates_in_headings_give_the_period_end() -> None:
    raw = b"Year ended May 31, 2026   Year ended May 31, 2025\nTotal assets 100 90\nTotal current assets 60 55\nTotal current liabilities 30 28\n"
    found = extract("s.txt", "text/plain", raw)
    assert found.period_end_guesses == ["2026-05-31", "2025-05-31"]


def test_unreadable_files_are_refused_plainly() -> None:
    with pytest.raises(UnreadableFile):
        extract("scan.png", "image/png", b"\x89PNG\r\n")
    with pytest.raises(UnreadableFile):
        extract("broken.pdf", "application/pdf", b"%PDF-1.4 not really")
    with pytest.raises(UnreadableFile):
        extract("empty.txt", "text/plain", b"   \n  ")
    with pytest.raises(UnreadableFile):
        extract("broken.xlsx", "application/zip", b"nope")
