"""The written-up analysis (Step 1): the five analyst dimensions with their figures and reference
ranges, extra red flags, the debt-service and sensitivity blocks, key concerns. Pure functions over
figures; no database."""

import pytest

from app.analysis import assess as rules
from app.analysis.dimensions import dimension_metrics
from app.analysis.facts import extract, to_figures
from app.analysis.ratios import Figures, compute
from app.analysis.report import (
    FINDING_WORD,
    build_report,
    debt_service_block,
    extra_flags,
    stress_block,
)
from app.recommendation.analysis_report import AnalysisReport
from tests.test_analyzer_rules import DISTRESSED, STRONG, facts_json


def figures_for(profile: dict[str, list[float | None]]) -> list[Figures]:
    years = extract(facts_json(profile), 3)
    return [
        to_figures(y, years[i + 1] if i + 1 < len(years) else None) for i, y in enumerate(years)
    ]


def report_for(figs: list[Figures]) -> AnalysisReport:
    contexts = [rules.YearContext(ratios=compute(f), figures=f) for f in figs]
    sections = rules.assess(contexts, "USD")
    return build_report(
        sections=sections,
        order=rules.SECTIONS,
        consolidated=rules.consolidated(sections),
        ratio_sets=[c.ratios for c in contexts],
        figure_sets=figs,
        periods=["2026-05-31", "2025-05-31", "2024-05-31"][: len(figs)],
        currency="USD",
        statements_label="test statements",
        audit_note="Audit status is not stated.",
        other_checks=[],
        gaps=["Gap A", "Gap A", "Gap B"],
        analyzer_version="2",
    )


def test_strong_and_distressed_figures_give_the_full_report() -> None:
    strong = report_for(figures_for(STRONG))
    assert [a.key for a in strong.areas] == [
        "liquidity",
        "profitability",
        "leverage",
        "cash_flow",
        "efficiency",
    ]
    assert [a.feeds_draft for a in strong.areas] == [True] * 4 + [False]  # the policy reads four
    assert [a.finding for a in strong.areas] == [
        "Strong",
        "Strong",
        "Strong",
        "Adequate",
        "Not assessed",
    ]
    assert strong.consolidated_status == "OK" and len(strong.red_flags) == 23
    assert strong.gaps == ["Gap A", "Gap B"]  # a repeated gap is listed once
    assert all(len(a.metrics) == len({m.label for m in a.metrics}) for a in strong.areas)
    liquidity = strong.areas[0]
    assert liquidity.metrics[0].earlier != "No earlier year"  # three periods are shown
    assert liquidity.metrics[0].reference == "1.5 to 2.0"  # the framework's reference range
    assert "four core dimensions" in strong.consolidated_why

    weak = report_for(figures_for(DISTRESSED))
    assert weak.consolidated_status == "DISTRESSED"
    assert {a.status for a in weak.areas if a.feeds_draft} == {"DISTRESSED"}
    assert weak.key_concerns[0].split(": ")[1].startswith("critical")  # the framework's word
    assert weak.executive_summary.startswith("Consolidated financial findings: distressed")
    assert all(
        not w.startswith("Efficiency") for w in weak.weaknesses
    )  # never assessed, not a weakness


def test_the_framework_words_map_to_the_status_colours() -> None:
    assert FINDING_WORD[rules.Level.STRONG] == "Strong"
    assert FINDING_WORD[rules.Level.SATISFACTORY] == "Adequate"
    assert FINDING_WORD[rules.Level.NEEDS_ATTENTION] == "Concerning"
    assert FINDING_WORD[rules.Level.WEAK] == "Critical"
    strong = report_for(figures_for(STRONG))
    weak = report_for(figures_for(DISTRESSED))
    # Strong and Adequate are OK (green), Concerning is WEAK (yellow), Critical is DISTRESSED (red).
    assert {a.status for a in strong.areas if a.feeds_draft} == {"OK"}
    assert {a.status for a in weak.areas if a.feeds_draft} == {"DISTRESSED"}


def test_sparse_figures_never_invent_a_number() -> None:
    report = report_for([{"revenue": 100.0}])
    assert {a.status for a in report.areas} == {"NOT_ASSESSED"}
    assert report.stress == [] and report.stress_note is None
    states = {f.text: f.state for f in report.red_flags}
    assert states["Negative shareholders' equity"] == "NOT_ASSESSABLE"
    assert report.debt_service_notes[-1].startswith("The debt maturity ladder")


def test_dimension_metrics_use_averages_and_never_default_to_zero() -> None:
    figs: list[Figures] = [
        {
            "revenue": 100.0,
            "net_income": 8.0,
            "total_assets": 200.0,
            "total_equity": 80.0,
            "ebitda": 15.0,
            "operating_income": 12.0,
            "gross_profit": 40.0,
            "inventory": 10.0,
            "capex": 6.0,
            "depreciation_amortisation": 4.0,
            "ocf": 12.0,
        },
        {
            "revenue": 90.0,
            "total_assets": 180.0,
            "total_equity": 70.0,
            "inventory": 8.0,
        },
    ]
    m = dimension_metrics(compute(figs[0]), figs[0], figs[1])
    assert m["profitability"]["net_margin"] == pytest.approx(0.08)
    assert m["profitability"]["return_on_assets"] == pytest.approx(8.0 / 190.0)  # average assets
    assert m["profitability"]["return_on_equity"] == pytest.approx(8.0 / 75.0)  # average equity
    assert m["profitability"]["growth"] == pytest.approx(100 / 90 - 1)
    assert m["efficiency"]["inventory_turnover"] == pytest.approx(60.0 / 9.0)  # cost of sales
    assert m["cash_flow"]["capex_to_depreciation"] == pytest.approx(1.5)
    assert m["leverage"]["debt_to_equity"] is None  # no debt figure: not calculable, not zero
    bare = dimension_metrics(compute({}), {}, None)
    assert all(v is None for group in bare.values() for v in group.values())


def test_extra_red_flags_answer_what_the_figures_can_and_say_what_they_cannot() -> None:
    figs: list[Figures] = [
        {
            "revenue": 100.0,
            "net_income": 5.0,
            "debt_due_12m": 30.0,
            "ocf": 3.0,
            "capex": 10.0,
            "ebitda": 12.0,
            "financial_debt": 400.0,
            "total_equity": 100.0,
            "cash": 5.0,
        },
        {
            "revenue": 100.0,
            "net_income": 12.0,
            "debt_due_12m": 10.0,
            "ocf": 14.0,
            "capex": 5.0,
            "ebitda": 20.0,
            "financial_debt": 40.0,
            "total_equity": 100.0,
            "cash": 10.0,
        },
    ]
    flags = {f.text: f for f in extra_flags([compute(f) for f in figs], figs, "USD")}
    assert flags["Debt to equity above 2.5"].state == "TRIGGERED"
    assert flags["Cash from operations below 80% of net income"].state == "TRIGGERED"
    assert (
        flags["Net margin down by more than 5 percentage points on the year before"].state
        == "TRIGGERED"
    )
    assert flags["Debt due within 12 months above 20% of annual revenue"].state == "TRIGGERED"
    assert flags["Negative free cash flow despite profitable operations"].state == "TRIGGERED"
    assert flags["Leverage rising while margins compress"].state == "TRIGGERED"
    for text in (
        "Largest customers above 50% of revenue",
        "Market share falling while the industry grows",
        "Covenant violations or near-misses",
    ):
        assert flags[text].state == "NOT_ASSESSABLE"


def test_extra_red_flags_are_not_assessable_without_the_figures() -> None:
    figs: list[Figures] = [{}]
    flags = extra_flags([compute({})], figs, "USD")
    assert {f.state for f in flags} == {"NOT_ASSESSABLE"}


def test_debt_service_block_states_what_it_cannot_see() -> None:
    figs: list[Figures] = [
        {
            "ocf": 30.0,
            "current_liabilities": 60.0,
            "debt_due_12m": 10.0,
            "interest_expense": 5.0,
            "cash": 20.0,
        }
    ]
    metrics, notes = debt_service_block([compute(figs[0])], figs, "USD")
    assert any("covers debt due within 12 months plus interest 2.00x" in n for n in notes)
    assert any("0.50x of current liabilities" in n for n in notes)
    assert notes[-1].startswith("The debt maturity ladder")
    assert metrics[0].label.startswith("Cash from operations over debt due")


def test_stress_is_arithmetic_with_its_assumption_stated() -> None:
    figs: list[Figures] = [
        {"revenue": 100.0, "operating_income": 20.0, "interest_expense": 5.0, "ocf": 15.0}
    ]
    rows, note = stress_block([compute(figs[0])], figs, "USD")
    assert [r.scenario for r in rows] == ["As reported", "Revenue down 10%", "Revenue down 20%"]
    assert rows[0].interest_cover == "4.00x"
    assert rows[1].earnings == "USD 10m" and rows[1].interest_cover == "2.00x"
    assert rows[2].earnings == "USD 0.00m" and rows[2].cash_from_operations == "-USD 5.00m"
    assert note is not None and "not a forecast" in note


def test_stress_is_skipped_without_revenue_or_earnings() -> None:
    assert stress_block([compute({})], [{}], "USD") == ([], None)
    no_interest: list[Figures] = [{"revenue": 100.0, "ebit": 10.0}]
    rows, _ = stress_block([compute(no_interest[0])], no_interest, "USD")
    assert (
        rows[0].interest_cover == "not calculable"
        and rows[0].cash_from_operations == "not available"
    )


def test_report_carries_no_outcome_or_score_wording() -> None:
    text = report_for(figures_for(DISTRESSED)).model_dump_json().lower()
    for word in ("approve", "decline", "credit limit", "covenant:", "loan term"):
        assert word not in text


def test_the_headline_is_never_ok_above_a_dimension_that_is_not() -> None:
    """Found on the live Nike case: '1 OK, 3 weak' was headlined OK because the policy's decline test
    (critical together) was not met. The policy test is unchanged; the headline now tells the truth."""
    thin = dict(STRONG)
    thin["NetIncomeLoss"] = [30, 35, 40]  # profitability becomes Concerning
    mixed = report_for(figures_for(thin))
    assert [a.status for a in mixed.areas if a.feeds_draft] == ["OK", "WEAK", "OK", "OK"]
    assert mixed.consolidated_status == "WEAK" and mixed.consolidated_finding == "Concerning"
    assert mixed.executive_summary.startswith("Consolidated financial findings: weak")
    strong = report_for(figures_for(STRONG))
    assert strong.consolidated_status == "OK" and strong.consolidated_finding == "Adequate"
    critical = report_for(figures_for(DISTRESSED))
    assert (
        critical.consolidated_status == "DISTRESSED" and critical.consolidated_finding == "Critical"
    )
    bare = report_for([{"revenue": 100.0}])
    assert (
        bare.consolidated_status == "NOT_ASSESSED" and bare.consolidated_finding == "Not assessed"
    )
