"""Analyzer v1: figure extraction, ratio method, section assessments and the amount proposal."""

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.analysis import assess as rules
from app.analysis.assess import Level
from app.analysis.facts import extract, to_figures
from app.analysis.ratios import compute

# The project's own ratio script (the five-area method). It lives here, not in the skill folder, so
# the check does not depend on which version of the analyst skill is installed.
SKILL_SCRIPT = Path(__file__).resolve().parent / "reference" / "calculate_ratios.py"
ENDS = ["2024-05-31", "2025-05-31", "2026-05-31"]


def facts_json(profile: dict[str, list[float | None]], form: str = "10-K") -> dict[str, Any]:
    """A small SEC company-facts document. Values are in millions, oldest year first."""
    flows = {
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "NetIncomeLoss",
        "OperatingIncomeLoss",
        "InterestExpense",
        "DepreciationDepletionAndAmortization",
        "NetCashProvidedByUsedInOperatingActivities",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsOfDividendsCommonStock",
        "PaymentsForRepurchaseOfCommonStock",
    }
    us_gaap: dict[str, Any] = {}
    for tag, values in profile.items():
        rows = []
        for end, value in zip(ENDS, values, strict=True):
            if value is None:
                continue
            row: dict[str, Any] = {
                "end": end,
                "val": int(value * 1_000_000),
                "form": form,
                "fp": "FY",
                "filed": f"{end[:4]}-07-15",
                "accn": f"0000000000-{end[2:4]}-000001",
            }
            if tag in flows:
                row["start"] = f"{int(end[:4]) - 1}-06-01"
            rows.append(row)
        us_gaap[tag] = {"units": {"USD": rows}}
    return {"facts": {"us-gaap": us_gaap}}


STRONG: dict[str, list[float | None]] = {
    "Assets": [1000, 1050, 1100],
    "StockholdersEquity": [500, 540, 600],
    "AssetsCurrent": [600, 640, 700],
    "LiabilitiesCurrent": [250, 260, 270],
    "CashAndCashEquivalentsAtCarryingValue": [200, 220, 260],
    "InventoryNet": [100, 100, 100],
    "AccountsReceivableNetCurrent": [110, 115, 120],
    "LongTermDebtNoncurrent": [100, 100, 90],
    "LongTermDebtCurrent": [0, 0, 0],
    "RevenueFromContractWithCustomerExcludingAssessedTax": [1000, 1040, 1090],
    "NetIncomeLoss": [100, 110, 120],
    "OperatingIncomeLoss": [150, 160, 170],
    "InterestExpense": [10, 10, 9],
    "DepreciationDepletionAndAmortization": [30, 30, 30],
    "NetCashProvidedByUsedInOperatingActivities": [140, 150, 160],
    "PaymentsToAcquirePropertyPlantAndEquipment": [40, 40, 40],
    "PaymentsOfDividendsCommonStock": [30, 30, 30],
    "PaymentsForRepurchaseOfCommonStock": [20, 20, 20],
}
DISTRESSED: dict[str, list[float | None]] = {
    "Assets": [800, 700, 600],
    "StockholdersEquity": [60, 10, -50],
    "AssetsCurrent": [300, 220, 150],
    "LiabilitiesCurrent": [280, 300, 320],
    "CashAndCashEquivalentsAtCarryingValue": [50, 30, 10],
    "InventoryNet": [150, 140, 130],
    "AccountsReceivableNetCurrent": [90, 130, 200],
    "LongTermDebtNoncurrent": [300, 320, 340],
    "LongTermDebtCurrent": [100, 120, 150],
    "RevenueFromContractWithCustomerExcludingAssessedTax": [900, 800, 700],
    "NetIncomeLoss": [10, -30, -80],
    "OperatingIncomeLoss": [40, 5, -20],
    "InterestExpense": [25, 30, 35],
    "DepreciationDepletionAndAmortization": [30, 30, 30],
    "NetCashProvidedByUsedInOperatingActivities": [30, 5, -20],
    "PaymentsToAcquirePropertyPlantAndEquipment": [20, 15, 10],
    "PaymentsOfDividendsCommonStock": [10, 5, 0],
    "PaymentsForRepurchaseOfCommonStock": [0, 0, 0],
}


def contexts(profile: dict[str, list[float | None]]) -> list[rules.YearContext]:
    years = extract(facts_json(profile))
    figs = [
        to_figures(y, years[i + 1] if i + 1 < len(years) else None) for i, y in enumerate(years)
    ]
    return [rules.YearContext(ratios=compute(f), figures=f) for f in figs]


def levels(profile: dict[str, list[float | None]]) -> dict[str, Level]:
    return {k: s.level for k, s in rules.assess(contexts(profile)).items()}


def test_extraction_uses_annual_dollar_figures_newest_first_in_millions() -> None:
    years = extract(facts_json(STRONG))
    assert [y.period_end.isoformat() for y in years] == ["2026-05-31", "2025-05-31", "2024-05-31"]
    assert years[0].values["total_assets"] == 1100.0 and years[0].values["revenue"] == 1090.0
    assert years[0].tags["total_equity"] == "StockholdersEquity" and years[0].accession


def test_quarterly_and_non_annual_rows_are_ignored() -> None:
    assert extract(facts_json(STRONG, form="10-Q")) == []
    doc = facts_json(STRONG)
    for row in doc["facts"]["us-gaap"]["RevenueFromContractWithCustomerExcludingAssessedTax"][
        "units"
    ]["USD"]:
        row["start"] = row["end"][:4] + "-03-01"  # a three-month window is not a year
    assert extract(doc)[0].values["revenue"] is None


def test_missing_tags_stay_missing_and_ratios_are_not_calculable() -> None:
    profile = {k: v for k, v in STRONG.items() if k != "AccountsReceivableNetCurrent"}
    ctx = contexts(profile)
    assert ctx[0].ratios["receivables"]["dso_days"] is None
    assert rules.assess(ctx)["receivables"].level is Level.NOT_ASSESSED


@pytest.mark.skipif(
    not SKILL_SCRIPT.exists(), reason="the local skill folder is not part of the repository"
)
def test_ratios_match_the_skill_script_exactly(tmp_path: Path) -> None:
    figures = contexts(STRONG)[0].figures
    path = tmp_path / "figures.json"
    path.write_text(json.dumps(figures), encoding="utf-8")
    run = subprocess.run(  # noqa: S603 - our own script, fixed arguments
        [sys.executable, "-I", str(SKILL_SCRIPT), str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    script = json.loads(run.stdout)
    mine = compute(figures)
    checked = 0
    for area, values in script.items():
        for name, value in values.items():
            if name in mine[area] and value is not None:
                assert mine[area][name] == pytest.approx(value), (area, name)
                checked += 1
    assert checked >= 15


def test_a_strong_company_is_described_as_strong_and_stable() -> None:
    sections = rules.assess(contexts(STRONG))
    assert sections["balance_sheet"].level is Level.STRONG
    assert sections["gearing"].level is Level.STRONG
    assert sections["liquidity"].level in (Level.STRONG, Level.SATISFACTORY)
    assert (
        sections["receivables"].level is Level.SATISFACTORY
    )  # never "strong" without an aging schedule
    assert rules.consolidated(sections)[0] in (Level.STRONG, Level.SATISFACTORY)
    assert all("not disclosed" in " ".join(s.flags) or not s.flags for s in sections.values())


def test_a_distressed_company_is_weak_and_the_consolidated_finding_follows_the_policy() -> None:
    sections = rules.assess(contexts(DISTRESSED))
    assert sections["balance_sheet"].level is Level.WEAK  # negative equity
    assert sections["liquidity"].level is Level.WEAK  # current ratio under 1
    assert sections["gearing"].level is Level.WEAK
    assert sections["cash_flow"].level is Level.WEAK
    level, why = rules.consolidated(sections)
    assert level is Level.WEAK and "4 of the 4" in why
    assert "Negative equity (a shareholders' deficit)" in sections["balance_sheet"].flags
    assert sections["liquidity"].trend == "Stable"  # weak the year before too


def test_consolidated_is_weak_only_when_the_core_sections_are_weak_together() -> None:
    sections = rules.assess(contexts(STRONG))
    sections["balance_sheet"].level = Level.WEAK
    sections["liquidity"].level = Level.WEAK
    assert (
        rules.consolidated(sections)[0] is Level.SATISFACTORY
    )  # two weak core sections are not enough
    sections["gearing"].level = Level.WEAK
    assert rules.consolidated(sections)[0] is Level.WEAK


def test_a_narrowing_cushion_is_reported_as_weakening() -> None:
    profile = dict(STRONG)
    profile["LiabilitiesCurrent"] = [250, 250, 400]  # current ratio 2.4 -> 1.75
    sections = rules.assess(contexts(profile))
    assert sections["liquidity"].level is Level.SATISFACTORY
    assert sections["liquidity"].trend == "Weakening"


def test_receivables_building_faster_than_sales_needs_attention() -> None:
    profile = dict(STRONG)
    profile["AccountsReceivableNetCurrent"] = [110, 115, 150]
    sections = rules.assess(contexts(profile))
    assert sections["receivables"].level is Level.NEEDS_ATTENTION
    assert any("faster than revenue" in f for f in sections["receivables"].flags)


def test_cash_flow_below_earnings_with_distributions_uncovered_needs_attention() -> None:
    profile = dict(STRONG)
    profile["NetCashProvidedByUsedInOperatingActivities"] = [140, 150, 80]
    sections = rules.assess(contexts(profile))
    assert sections["cash_flow"].level is Level.NEEDS_ATTENTION
    assert any("below net income" in f for f in sections["cash_flow"].flags)


def test_assessments_are_described_in_words_only() -> None:
    for section in rules.assess(contexts(STRONG)).values():
        assert section.level.value in {
            "STRONG",
            "SATISFACTORY",
            "NEEDS_ATTENTION",
            "WEAK",
            "NOT_ASSESSED",
        }
        assert section.trend in {"Improving", "Stable", "Weakening", "No earlier year to compare"}


def test_the_proposal_starts_at_the_whole_amount_and_each_gap_costs_a_fixed_share() -> None:
    sections = rules.assess(contexts(STRONG))
    fraction, factors = rules.propose_fraction(
        sections, adverse_search_complete=True, sector_outlook_assessed=True
    )
    assert fraction == Decimal(1) and factors == []

    fraction, factors = rules.propose_fraction(
        sections, adverse_search_complete=False, sector_outlook_assessed=False
    )
    assert fraction == Decimal("0.90")
    assert [f.code for f in factors] == ["missing_information"]


def test_weak_sections_cost_more_and_the_proposal_never_goes_below_zero() -> None:
    sections = rules.assess(contexts(DISTRESSED))
    fraction, factors = rules.propose_fraction(
        sections, adverse_search_complete=False, sector_outlook_assessed=False
    )
    assert Decimal(0) <= fraction < Decimal("0.20")
    assert {f.code for f in factors} == {"acceptable_not_strong", "missing_information"}


def test_money_helpers_show_currency_and_billions() -> None:
    assert rules.money(9027.0, "USD") == "USD 9.03bn"
    assert rules.money(-369.0, "USD") == "-USD 369m"
    assert rules.money(1085.0, "CAD") == "CAD 1.09bn"
    assert rules.money(0.75, "CAD") == "CAD 0.75m"
    assert rules.money(1.0, "CAD") == "CAD 1.00m"
    assert rules.money(None) == "not available"
