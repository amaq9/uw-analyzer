"""Per-dimension paragraphs, the cash conversion cycle and the executive summary for the decision-maker.
Pure functions over figures; no database."""

import datetime as dt
import uuid

import pytest

from app.analysis import assess as rules
from app.analysis.brief import Recommendation
from app.analysis.cycle import NO_INVENTORY, build_cash_cycle, period_figures
from app.analysis.narrative import Measure, summarise
from app.analysis.ratios import Figures, compute
from app.ratings.schemas import PublishedRatingOut
from app.recommendation.analysis_report import AnalysisReport
from tests.test_analysis_report import figures_for, report_for
from tests.test_analyzer_rules import DISTRESSED, STRONG


def cycle_year(**over: float | None) -> Figures:
    base: Figures = {
        "revenue": 1000.0,
        "receivables": 100.0,
        "cost_of_revenue": 600.0,
        "inventory": 150.0,
        "payables": 80.0,
        "days_in_period": 365.0,
    }
    return {**base, **over}


PERIODS = ["2026-05-31", "2025-05-31", "2024-05-31"]


# --- the order and the names -----------------------------------------------------------------------


def test_profitability_comes_first_and_leverage_is_called_balance_sheet_and_leverage() -> None:
    assert rules.SECTIONS == ("profitability", "liquidity", "leverage", "cash_flow", "efficiency")
    assert rules.CORE == ("profitability", "liquidity", "leverage", "cash_flow")
    assert rules.TITLES["leverage"] == "Balance sheet and leverage"
    report = report_for(figures_for(STRONG))
    assert [a.title for a in report.areas] == [
        "Profitability",
        "Liquidity",
        "Balance sheet and leverage",
        "Cash flow",
        "Efficiency and sector",
    ]


# --- the paragraph on why a dimension stands where it does -----------------------------------------


NIKE_LIQUIDITY = [
    Measure("Current ratio", 1.96, 2.21, "times", 2, "1.5 to 2.0 is adequate"),
    Measure("Quick ratio", 1.36, 1.50, "times", 3, "above 1.2 is strong"),
    Measure(
        "Cash from operations over current liabilities",
        0.23,
        0.35,
        "times",
        1,
        "0.30 to 0.50 is adequate",
    ),
    Measure("Cash less debt due within 12 months", 7030.0, 9150.0, "money", None, "positive"),
]


def test_the_paragraph_names_the_weakest_measure_what_is_better_what_moved_and_the_cut() -> None:
    text = summarise(
        title="Liquidity",
        level="NEEDS_ATTENTION",
        trend="Weakening",
        earlier_level="SATISFACTORY",
        measures=NIKE_LIQUIDITY,
        currency="USD",
        cut_percent=5,
        core=True,
    )
    assert text.startswith(
        "Liquidity is rated Concerning (shown as Weak) because it is judged by its weakest measure"
    )
    assert "cash from operations over current liabilities is 0.23x, which is concerning" in text
    assert "The other measures are better" not in text  # one of them is shown for context only
    assert (
        "Other measures: current ratio 1.96x (adequate)" in text
        and "quick ratio 1.36x (strong)" in text
    )
    assert "moved from adequate to concerning" in text
    assert (
        "current ratio 2.21x to 1.96x" in text
        and "cash from operations over current liabilities 0.35x to 0.23x" in text
    )
    assert text.endswith(
        "This lowers the UW Analyzer's proposed amount by 5% of the amount requested."
    )


def test_a_strong_dimension_says_so_and_a_stable_one_says_unchanged() -> None:
    strong = [
        Measure("Debt to equity", 0.74, 0.8, "times", 3, "below 1.0", higher_is_better=False),
        Measure("Interest cover", 11.9, 10.0, "times", 3, "above 4.0"),
    ]
    text = summarise(
        title="Balance sheet and leverage",
        level="STRONG",
        trend="Stable",
        earlier_level="STRONG",
        measures=strong,
        currency="USD",
        cut_percent=None,
        core=True,
    )
    assert "every rated measure is strong: debt to equity 0.74x and interest cover 11.90x" in text
    assert "unchanged from the year before" in text
    assert text.endswith("This does not lower the UW Analyzer's proposed amount.")


def test_an_adequate_dimension_lists_its_weakest_measures_as_inside_the_range() -> None:
    text = summarise(
        title="Cash flow",
        level="SATISFACTORY",
        trend="No earlier year to compare",
        earlier_level=None,
        measures=[
            Measure("Free cash flow as a share of revenue", 0.12, None, "pct", 2, "10% to 20%")
        ],
        currency="USD",
        cut_percent=None,
        core=True,
    )
    assert (
        "no measure is concerning, and the weakest is: free cash flow as a share of revenue is 12.0%"
        in text
    )


@pytest.mark.parametrize("profile", [STRONG, DISTRESSED])
def test_the_measures_always_agree_with_the_finding(profile: dict[str, list[float | None]]) -> None:
    figs = figures_for(profile)
    for i, f in enumerate(figs):
        ctx = rules.YearContext(
            ratios=compute(f), figures=f, prior_figures=figs[i + 1] if i + 1 < len(figs) else None
        )
        prior = (
            None
            if i + 1 >= len(figs)
            else rules.YearContext(
                ratios=compute(figs[i + 1]),
                figures=figs[i + 1],
                prior_figures=figs[i + 2] if i + 2 < len(figs) else None,
            )
        )
        for key, section in rules.assess_year(ctx, prior, "USD").items():
            banded = [
                m.band for m in section.measures if m.band is not None and m.value is not None
            ]
            if section.level is rules.Level.NOT_ASSESSED or not banded:
                continue
            assert rules.BAND_LEVEL[min(banded)] is section.level, (key, i)


def test_every_core_dimension_in_the_report_carries_its_paragraph() -> None:
    for profile in (STRONG, DISTRESSED):
        report = report_for(figures_for(profile))
        for area in report.areas:
            assert area.summary, area.key
            if area.feeds_draft:
                assert "proposed amount" in area.summary
        assert "peer data" in (report.areas[-1].summary or "").lower() or "not connected" in (
            report.areas[-1].summary or ""
        )


# --- the cash conversion cycle ---------------------------------------------------------------------


def test_the_cycle_is_calculated_for_each_period_with_its_movement() -> None:
    figs = [
        cycle_year(),
        cycle_year(receivables=80.0, inventory=140.0, payables=90.0),
        cycle_year(receivables=70.0, inventory=130.0, payables=70.0),
    ]
    cc = build_cash_cycle(figs, PERIODS, [])
    assert cc is not None
    rows = {r.key: r for r in cc.rows}
    assert (
        rows["dso"].current == "36.5 days"
        and rows["dso"].prior == "29.2 days"
        and rows["dso"].earlier == "25.6 days"
    )
    assert rows["dio"].current == "91.2 days" and rows["dpo"].current == "48.7 days"
    assert rows["ccc"].current == "79.1 days"  # 36.5 + 91.2 - 48.7
    assert (
        rows["dso"].movement == "Longer by 7.3 days (slower collection)"
        and rows["dso"].direction == "worse"
    )
    assert rows["dpo"].direction == "worse"  # shorter payables: less cash held
    assert rows["ccc"].movement.startswith("Longer by") and rows["ccc"].direction == "worse"
    assert "collects from customers in 36.5 days (was 29.2 days)" in cc.summary
    assert "Cash is therefore tied up for 79.1 days" in cc.summary
    assert cc.periods == PERIODS


def test_a_shorter_cycle_is_better_and_a_longer_payment_period_helps_cash() -> None:
    figs = [cycle_year(receivables=60.0, payables=110.0), cycle_year()]
    cc = build_cash_cycle(figs, PERIODS, [])
    assert cc is not None
    rows = {r.key: r for r in cc.rows}
    assert rows["dso"].direction == "better" and rows["dpo"].direction == "better"
    assert rows["ccc"].direction == "better" and "Shorter by" in rows["ccc"].movement
    assert "shorter than the year before" in cc.summary


@pytest.mark.parametrize("inventory", [None, 0.0])
def test_a_company_with_no_inventory_leaves_dio_blank_and_says_why(inventory: float | None) -> None:
    figs = [cycle_year(inventory=inventory), cycle_year(inventory=inventory)]
    cc = build_cash_cycle(figs, PERIODS, [])
    assert cc is not None
    rows = {r.key: r for r in cc.rows}
    assert rows["dio"].current == NO_INVENTORY and rows["dio"].prior == NO_INVENTORY
    assert rows["dio"].movement == "Not applicable: no inventory"
    assert rows["ccc"].current == "-12.2 days"  # DSO 36.5 less DPO 48.7: no inventory term
    assert any("reports no inventory" in n for n in cc.notes)
    assert "holds no inventory" in cc.summary
    assert period_figures(figs[0])["no_inventory"] is True


def test_missing_payables_or_cost_of_sales_is_stated_never_estimated() -> None:
    no_payables = build_cash_cycle([cycle_year(payables=None)], PERIODS, [])
    assert no_payables is not None
    rows = {r.key: r for r in no_payables.rows}
    assert rows["dpo"].current == "not available" and rows["ccc"].current == "not available"
    assert any("Trade payables were not available" in n for n in no_payables.notes)
    assert "could not be calculated" in no_payables.summary
    no_cost = build_cash_cycle([cycle_year(cost_of_revenue=None)], PERIODS, [])
    assert no_cost is not None
    assert {r.key: r for r in no_cost.rows}["dio"].current == "not calculable (no cost of sales)"
    assert any("Cost of sales is not available" in n for n in no_cost.notes)


def test_a_single_period_has_no_movement_and_nothing_to_calculate_gives_no_section() -> None:
    cc = build_cash_cycle([cycle_year()], PERIODS, [])
    assert cc is not None and all(r.movement == "No earlier year to compare" for r in cc.rows)
    assert all(r.prior is None for r in cc.rows)
    assert build_cash_cycle([{}], PERIODS, []) is None


def test_derived_inputs_are_flagged_in_the_notes() -> None:
    definitions = [
        "Inventory here is finished goods only (total inventory not tagged).",
        "Cost of sales here is revenue less gross profit (cost of sales not tagged).",
    ]
    cc = build_cash_cycle([cycle_year(), cycle_year()], PERIODS, definitions)
    assert cc is not None
    assert any("finished-goods figure" in n for n in cc.notes)
    assert any("revenue less gross profit" in n for n in cc.notes)


def test_the_report_carries_the_cycle_and_defines_its_terms() -> None:
    figs = figures_for(STRONG)
    for f in figs:  # the SEC fixture has no payables or cost of sales: add them
        f["payables"], f["cost_of_revenue"] = 100.0, (f.get("revenue") or 0) * 0.6
    report = report_for(figs)
    assert report.cash_cycle is not None and [r.key for r in report.cash_cycle.rows] == [
        "dso",
        "dio",
        "dpo",
        "ccc",
    ]
    assert any(d.startswith("Days sales outstanding (DSO)") for d in report.definitions)


# --- the executive summary -------------------------------------------------------------------------


def rating(
    agency: str, grade: str, outlook: str, change: str, source: str, ig: bool = True
) -> PublishedRatingOut:
    now = dt.datetime(2026, 10, 18, tzinfo=dt.UTC)
    return PublishedRatingOut(
        id=uuid.uuid4(),
        case_id=uuid.uuid4(),
        agency=agency,  # type: ignore[arg-type]
        grade=grade,
        investment_grade=ig,
        outlook=outlook,  # type: ignore[arg-type]
        under_review=False,
        change=change,  # type: ignore[arg-type]
        last_action_on=dt.date(2026, 10, 5),
        rationale=None,
        source_url=source,
        retrieved_at=now,
        quote="q",
        recorded_by="t",
        recorded_at=now,
    )


def approve_reduced() -> Recommendation:
    return Recommendation(
        outcome="APPROVE",
        band="REDUCED",
        amount=3_750_000.0,
        requested=5_000_000.0,
        proposed=3_750_000.0,
        currency="USD",
        factors=[
            (
                "acceptable_not_strong",
                "Not strong enough to support the whole amount: liquidity.",
                0.15,
            ),
            (
                "missing_information",
                "Information is missing: the sector outlook was not assessed.",
                0.10,
            ),
        ],
        rules=[],
    )


def briefed(rec: Recommendation, ratings: list[PublishedRatingOut] | None = None) -> AnalysisReport:
    figs = figures_for(DISTRESSED)
    contexts = [rules.YearContext(ratios=compute(f), figures=f) for f in figs]
    sections = rules.assess(contexts, "USD")
    from app.analysis.report import build_report

    return build_report(
        sections=sections,
        order=rules.SECTIONS,
        consolidated=rules.consolidated(sections),
        ratio_sets=[c.ratios for c in contexts],
        figure_sets=figs,
        periods=PERIODS,
        currency="USD",
        statements_label="test statements",
        audit_note="Audit status is not stated.",
        other_checks=[],
        gaps=["Sector outlook was not assessed"],
        analyzer_version="2",
        ratings=ratings,
        as_of=dt.date(2026, 10, 18),
        recommendation=rec,
        company="Acme Corp",
    )


def test_the_brief_leads_with_the_recommendation_and_the_amounts() -> None:
    brief = briefed(approve_reduced()).executive_brief
    assert brief is not None
    assert brief.headline.startswith("Approve a reduced USD 3.75m, 75% of the USD 5.00m requested.")
    rec = next(s for s in brief.sections if s.heading == "Recommendation")
    assert "The reduction comes from" in rec.text and "(-15%)" in rec.text and "(-10%)" in rec.text
    headings = [s.heading for s in brief.sections]
    assert headings[:3] == [
        "Recommendation",
        "How the four core dimensions stand",
        "Financial position in numbers",
    ]
    for needed in (
        "What the rating agencies say",
        "Screening and external checks",
        "Annual report notes and auditor",
        "What is not known",
    ):
        assert needed in headings


def test_the_brief_gives_the_critical_numbers() -> None:
    brief = briefed(approve_reduced()).executive_brief
    assert brief is not None
    numbers = next(s for s in brief.sections if s.heading == "Financial position in numbers").text
    for word in (
        "Revenue",
        "net margin",
        "EBITDA margin",
        "Cash from operations",
        "free cash flow",
        "Current ratio",
        "Debt to equity",
        "interest cover",
    ):
        assert word in numbers
    assert "USD" in numbers


def test_a_decline_is_stated_with_its_rule() -> None:
    rec = Recommendation(
        "DECLINE", "DECLINE", None, 5_000_000.0, 0.0, "USD", [], ["financial_findings_weak"]
    )
    brief = briefed(rec).executive_brief
    assert brief is not None
    assert brief.headline.startswith("Decline. The UW Analyzer recommends no credit for Acme Corp")
    assert "financial findings weak" in brief.headline


def test_agency_ratings_are_in_the_brief_with_their_outlook_and_source_quality() -> None:
    ratings = [
        rating("MOODYS", "A2", "NEGATIVE", "NOT_STATED", "https://example.org/moodys"),
        rating("SP", "A", "NEGATIVE", "DOWNGRADE", "https://example.org/sp"),
    ]
    brief = briefed(approve_reduced(), ratings).executive_brief
    assert brief is not None
    text = next(s for s in brief.sections if s.heading == "What the rating agencies say").text
    assert "Moody's A2 (negative outlook" in text and "S&P A (downgraded, negative outlook" in text
    assert "secondary sources" in text and "do not change the amount" in text
    assert "rating agencies have turned cautious" in brief.headline
    assert any("Confirm the agency ratings" in p for p in brief.points_to_settle)


def test_with_no_ratings_and_no_filing_the_brief_says_so() -> None:
    brief = briefed(approve_reduced()).executive_brief
    assert brief is not None
    by = {s.heading: s.text for s in brief.sections}
    assert "No published agency rating is recorded" in by["What the rating agencies say"]
    assert "was not read in this run" in by["Annual report notes and auditor"]
    assert "No screening results were recorded" in by["Screening and external checks"]
    assert brief.points_to_settle  # triggered checks become points to settle


def test_no_brief_without_a_recommendation() -> None:
    assert report_for(figures_for(STRONG)).executive_brief is None


def test_a_brief_stored_under_the_earlier_field_name_is_still_readable() -> None:
    # Found live: a draft stored while the field was called decision_points broke the whole list when renamed.
    from app.recommendation.analysis_report import ExecutiveBrief

    old = {"headline": "H", "sections": [], "decision_points": ["Ask about collections."]}
    assert ExecutiveBrief.model_validate(old).points_to_settle == ["Ask about collections."]
    new = {"headline": "H", "sections": [], "points_to_settle": ["Ask."]}
    assert ExecutiveBrief.model_validate(new).points_to_settle == ["Ask."]
