"""The written-up analysis (Step 1): profitability and efficiency context, extra red flags, the
debt-service and sensitivity blocks, key concerns. Pure functions over figures; no database."""

from typing import Any

import pytest

from app.analysis import assess as rules
from app.analysis.facts import extract, to_figures
from app.analysis.ratios import Figures, compute
from app.analysis.report import (
    build_report,
    efficiency_area,
    extra_flags,
    profitability_area,
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
        analyzer_version="1",
    )


def margin_figs(net_incomes: list[float | None], revenue: float = 100.0) -> list[Figures]:
    """Newest first, each year with the same revenue and the given net income."""
    return [
        {"revenue": revenue, "net_income": ni, "total_assets": 200.0, "total_equity": 80.0}
        for ni in net_incomes
    ]


def test_strong_and_distressed_figures_give_the_full_report() -> None:
    strong = report_for(figures_for(STRONG))
    assert [a.key for a in strong.areas][-2:] == ["profitability", "efficiency"]
    assert [a.feeds_draft for a in strong.areas] == [True] * 5 + [False] * 2
    assert strong.consolidated_status == "OK" and len(strong.red_flags) == 16
    assert strong.gaps == ["Gap A", "Gap B"]  # a repeated gap is listed once
    assert all(len(a.metrics) == len({m.label for m in a.metrics}) for a in strong.areas)
    liquidity = next(a for a in strong.areas if a.key == "liquidity")
    assert liquidity.metrics[0].earlier != "No earlier year"  # three periods are shown

    weak = report_for(figures_for(DISTRESSED))
    assert weak.consolidated_status == "DISTRESSED"
    assert weak.key_concerns[0].split(": ")[1].startswith("distressed")
    assert weak.executive_summary.startswith("Consolidated financial findings: distressed")


def test_sparse_figures_never_invent_a_number() -> None:
    report = report_for([{"revenue": 100.0}])
    assert {a.status for a in report.areas} == {"NOT_ASSESSED"}
    assert report.stress == [] and report.stress_note is None
    states = {f.text: f.state for f in report.red_flags}
    assert states["Negative shareholders' equity"] == "NOT_ASSESSABLE"
    assert report.debt_service_notes[-1].startswith("The debt maturity ladder")


@pytest.mark.parametrize(
    ("net_incomes", "status", "finding"),
    [
        ([1.0, 1.0], "DISTRESSED", "Weak"),  # below 2%
        ([3.0, 3.0], "WEAK", "Needs attention"),  # 2 to 5%
        ([7.0, 7.0], "OK", "Satisfactory"),  # 5 to 10%
        ([12.0, 12.0], "OK", "Strong"),  # above 10% and not falling
        ([12.0, 14.0], "OK", "Satisfactory"),  # above 10% but down on the year
        ([-4.0, 3.0], "DISTRESSED", "Weak"),  # a loss
    ],
)
def test_profitability_follows_the_net_margin_thresholds(
    net_incomes: list[float | None], status: str, finding: str
) -> None:
    area = profitability_area(margin_figs(net_incomes), "USD")
    assert (area.status, area.finding) == (status, finding)
    assert area.feeds_draft is False and "does not change the draft amount" in area.why


def test_a_big_margin_fall_is_flagged_and_downgrades_a_healthy_margin() -> None:
    area = profitability_area(margin_figs([9.0, 16.0]), "USD")  # 9% from 16%: seven points
    assert "Net margin fell by more than 5 percentage points" in area.flags
    assert (area.status, area.trend) == ("WEAK", "Weakening")


def test_profitability_without_two_years_has_no_trend() -> None:
    area = profitability_area(margin_figs([8.0]), "USD")
    assert area.trend == "No earlier year to compare" and area.status == "OK"
    missing = profitability_area([{"revenue": 100.0}], "USD")
    assert missing.status == "NOT_ASSESSED"


def test_efficiency_is_shown_but_never_given_a_status() -> None:
    figs: list[Figures] = [
        {
            "revenue": 100.0,
            "gross_profit": 40.0,
            "inventory": 10.0,
            "total_assets": 200.0,
            "receivables": 12.0,
        },
        {
            "revenue": 90.0,
            "gross_profit": 36.0,
            "inventory": 8.0,
            "total_assets": 180.0,
            "receivables": 10.0,
        },
    ]
    ratio_sets = [compute(f) for f in figs]
    area = efficiency_area(ratio_sets, figs, "USD")
    labels = {m.label for m in area.metrics}
    assert area.status == "NOT_ASSESSED" and area.feeds_draft is False
    assert "Asset turnover (revenue over average assets)" in labels
    assert "Inventory turnover (cost of sales over average inventory)" in labels


def test_extra_red_flags_answer_what_the_figures_can_and_say_what_they_cannot() -> None:
    figs: list[Figures] = [
        {
            "revenue": 100.0,
            "net_income": 5.0,
            "debt_due_12m": 30.0,
            "ocf": 4.0,
            "capex": 10.0,
            "ebitda": 12.0,
            "financial_debt": 60.0,
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
            "cash": 10.0,
        },
    ]
    flags = {f.text: f for f in extra_flags([compute(f) for f in figs], figs, "USD")}
    assert (
        flags["Net margin down by more than 5 percentage points on the year before"].state
        == "TRIGGERED"
    )
    assert flags["Debt due within 12 months above 20% of annual revenue"].state == "TRIGGERED"
    assert flags["Negative free cash flow despite profitable operations"].state == "TRIGGERED"
    assert flags["Leverage rising while margins compress"].state == "TRIGGERED"
    assert flags["Largest customers above 50% of revenue"].state == "NOT_ASSESSABLE"
    assert flags["Market share falling while the industry grows"].state == "NOT_ASSESSABLE"


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
    text: Any = report_for(figures_for(DISTRESSED)).model_dump_json().lower()
    for word in ("approve", "decline", "credit limit", "covenant:", "loan term"):
        assert word not in text
