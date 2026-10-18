"""The 10-K reader: what it concludes from the filing's own words, and what it must never conclude."""

import hashlib

import pytest

from app.analysis.notes import scan, sentences, text_of
from app.analysis.report import (
    COVENANT_CHECK,
    CUSTOMER_CHECK,
    GOING_CONCERN_CHECK,
    notes_flags,
)
from tests.filing_fixtures import filing_html


def read(**kwargs: str):  # type: ignore[no-untyped-def]
    return scan(
        filing_html(**kwargs),
        label="Acme 10-K",
        url="https://www.sec.gov/x.htm",
        filed="2026-07-15",
    )


def topic(result, key: str):  # type: ignore[no-untyped-def]
    return next(f for f in result.review.findings if f.topic == key)


def test_a_clean_filing_raises_no_concern_and_quotes_what_reassures() -> None:
    result = read()
    states = {f.topic: f.state for f in result.review.findings}
    assert states["GOING_CONCERN"] == "NO_CONCERN"
    assert states["AUDITOR_OPINION"] == "NO_CONCERN"
    assert states["AUDITOR_CHANGE"] == "NO_CONCERN"
    assert states["COVENANTS"] == "NO_CONCERN"
    assert states["CUSTOMER_CONCENTRATION"] == "NO_CONCERN"
    assert states["INTERNAL_CONTROL"] == "NO_CONCERN"
    assert not [s for s in states.values() if s == "CONCERN"]
    assert result.review.summary.startswith("No going-concern warning")
    assert result.review.sha256 == hashlib.sha256(filing_html()).hexdigest()
    audit = topic(result, "AUDITOR_OPINION")
    assert "Example Audit LLP" in audit.summary
    assert audit.quotes[0].text.startswith(
        "In our opinion, the consolidated financial statements present fairly"
    )


def test_risk_factor_boilerplate_and_hidden_text_never_raise_a_concern() -> None:
    # The fixture's risk factors say a breach "could raise substantial doubt"; a hidden XBRL header and a script
    # also contain the warning words. None of that is a statement of fact about this company.
    result = read(covenants="hypothetical")
    assert topic(result, "GOING_CONCERN").state == "NO_CONCERN"
    assert (
        "neither appears" not in topic(result, "GOING_CONCERN").summary
    )  # the risk factor does mention it
    assert topic(result, "COVENANTS").state == "INFO"
    assert "not in compliance" not in text_of(filing_html())  # the script is dropped


def test_a_stated_going_concern_doubt_is_a_concern_with_the_filings_sentence() -> None:
    finding = topic(read(going_concern="doubt"), "GOING_CONCERN")
    assert finding.state == "CONCERN"
    assert finding.quotes[0].text.startswith("These conditions raise substantial doubt")
    negated = topic(read(going_concern="negated"), "GOING_CONCERN")
    assert negated.state == "NO_CONCERN" and "no substantial doubt" in negated.quotes[0].text


def test_a_covenant_breach_and_waiver_is_a_concern_but_compliance_is_not() -> None:
    breach = topic(read(covenants="breach"), "COVENANTS")
    assert breach.state == "CONCERN" and "waiver" in breach.quotes[0].text
    assert topic(read(covenants="complied"), "COVENANTS").state == "NO_CONCERN"
    assert (
        topic(read(covenants="silent"), "COVENANTS").state == "INFO"
    )  # only the risk-factor mentions


def test_qualified_auditor_wording_and_a_change_of_auditor_are_concerns() -> None:
    qualified = read(opinion="qualified")
    assert topic(qualified, "AUDITOR_OPINION").state == "CONCERN"
    assert topic(read(auditor_change="changed"), "AUDITOR_CHANGE").state == "CONCERN"
    missing = topic(read(opinion="missing"), "AUDITOR_OPINION")
    assert missing.state == "NOT_FOUND" and "could not be read" in missing.summary


def test_customer_share_is_read_from_the_filing_and_compared_with_fifty_percent() -> None:
    big = read(customers="big")
    finding = topic(big, "CUSTOMER_CONCENTRATION")
    assert finding.state == "CONCERN" and "62%" in finding.summary
    assert big.largest_customer_pct == 62.0
    none = read(customers="none_over_10")
    assert none.no_customer_over_10 and topic(none, "CUSTOMER_CONCENTRATION").state == "NO_CONCERN"
    assert topic(read(customers="silent"), "CUSTOMER_CONCENTRATION").state == "NOT_FOUND"


def test_a_material_weakness_is_a_concern() -> None:
    assert topic(read(material_weakness="weakness"), "INTERNAL_CONTROL").state == "CONCERN"


def test_facilities_allowance_legal_and_subsequent_events_are_quoted_for_a_person() -> None:
    result = read()
    assert "no borrowings were outstanding" in topic(result, "CREDIT_FACILITIES").quotes[0].text
    assert "$42 million" in topic(result, "ALLOWANCE").quotes[0].text
    assert (
        topic(result, "LEGAL").state == "INFO"
        and topic(result, "LEGAL").quotes[0].where == "Item 3"
    )
    assert topic(result, "SUBSEQUENT_EVENTS").state == "INFO"


def test_every_quote_is_a_sentence_that_really_is_in_the_filing() -> None:
    text = text_of(filing_html(covenants="breach", going_concern="doubt", customers="big"))
    result = read(covenants="breach", going_concern="doubt", customers="big")
    for finding in result.review.findings:
        for quote in finding.quotes:
            assert quote.text.rstrip("…") in text


def test_a_short_unreadable_text_says_the_review_may_be_incomplete() -> None:
    short = scan(
        b"<html><body><p>Nothing useful here at all, just a stub page.</p></body></html>",
        label="x",
        url=None,
        filed=None,
    )
    assert short.review.summary.startswith("The filing text is short or unreadable")


def test_sentence_splitting_keeps_decimals_and_drops_fragments() -> None:
    got = sentences(
        "The facility is $2.5 billion and matures in 2029. Short.\nAnother complete sentence follows here."
    )
    assert got == [
        "The facility is $2.5 billion and matures in 2029.",
        "Another complete sentence follows here.",
    ]


@pytest.mark.parametrize(
    ("kwargs", "check", "state"),
    [
        ({}, GOING_CONCERN_CHECK, "CLEAR"),
        ({"going_concern": "doubt"}, GOING_CONCERN_CHECK, "TRIGGERED"),
        ({"covenants": "breach"}, GOING_CONCERN_CHECK, "TRIGGERED"),
        ({"opinion": "missing"}, GOING_CONCERN_CHECK, "NOT_ASSESSABLE"),
        ({}, CUSTOMER_CHECK, "CLEAR"),
        ({"customers": "big"}, CUSTOMER_CHECK, "TRIGGERED"),
        ({"customers": "silent"}, CUSTOMER_CHECK, "NOT_ASSESSABLE"),
        ({}, COVENANT_CHECK, "CLEAR"),
        ({"covenants": "breach"}, COVENANT_CHECK, "TRIGGERED"),
        ({"covenants": "silent"}, COVENANT_CHECK, "NOT_ASSESSABLE"),
    ],
)
def test_the_checklist_items_only_the_filing_can_answer(
    kwargs: dict[str, str], check: str, state: str
) -> None:
    flags = notes_flags(read(**kwargs).review)
    assert flags[check].state == state


def test_without_the_filing_the_checks_stay_not_assessable() -> None:
    assert notes_flags(None) == {}


REAL_STYLE = (
    "<html><body>"
    + "<p>The Company designs and sells products to customers around the world every year.</p>"
    * 400
    + "<p>Under these facilities, we have agreed to various covenants.</p>"
    "<p>As of May 31, 2026, we were in full compliance with each of these covenants, and we believe it is "
    "unlikely we will fail to meet any of these covenants in the foreseeable future.</p>"
    "<p>As of and for the periods ended May 31, 2026 and 2025, no amounts were outstanding under any of the "
    "Company's committed credit facilities.</p>"
    "<p>This facility replaced the prior $1 billion 364-day credit facility agreement, which matured on March 6, 2026.</p>"
    "<p>Amended and Restated Covenant Not to Compete and Non-Disclosure Agreement between the Company and an officer.</p>"
    "<p>The Company maintains an allowance for expected losses resulting from the inability of its customers to pay.</p>"
    "<p>During fiscal 2026, our three largest customers accounted for approximately 29% of sales.</p>"
    "<p>Item 9. Changes in and Disagreements with Accountants on Accounting and Financial Disclosure</p>"
    "<p>There has been no change of accountants nor any disagreements with accountants on any matter.</p>"
    "<p>Item 9A. Controls and Procedures</p></body></html>"
).encode()


def test_wording_found_in_a_real_filing_is_read_correctly() -> None:
    # Found by running the reader on a real 10-K: "May" the month is not the word "may", "any of" is not
    # hypothetical, "in full compliance" is a compliance statement, and "no change of accountants" means none.
    result = scan(REAL_STYLE, label="x", url=None, filed=None)
    by = {f.topic: f for f in result.review.findings}
    assert (
        by["COVENANTS"].state == "NO_CONCERN"
        and "full compliance" in by["COVENANTS"].quotes[0].text
    )
    assert all("Not to Compete" not in q.text for q in by["COVENANTS"].quotes)
    assert by["AUDITOR_CHANGE"].state == "NO_CONCERN"
    facility = by["CREDIT_FACILITIES"]
    assert facility.state == "INFO" and "no amounts were outstanding" in facility.quotes[0].text
    assert all("replaced the prior" not in q.text for q in facility.quotes)
    assert by["ALLOWANCE"].state == "INFO" and "states no amount" in by["ALLOWANCE"].summary
    assert "29%" in by["CUSTOMER_CONCENTRATION"].summary


def test_a_filing_declaring_ascii_but_carrying_windows_1252_text_is_read() -> None:
    body = "<html><body><p>See Note 16 – Commitments and Contingencies for more detail here.</p></body></html>".encode(
        "cp1252"
    )
    assert "Note 16 – Commitments" in text_of(body)
