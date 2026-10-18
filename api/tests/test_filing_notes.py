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
