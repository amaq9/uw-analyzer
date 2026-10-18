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
    assert ctx[0].figures["receivables"] is None  # nothing is defaulted to zero


@pytest.mark.skipif(not SKILL_SCRIPT.exists(), reason="the reference ratio script is missing")
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
    assert list(sections) == ["liquidity", "profitability", "leverage", "cash_flow", "efficiency"]
    assert sections["liquidity"].level is Level.STRONG
    assert sections["profitability"].level is Level.STRONG
    assert sections["leverage"].level is Level.STRONG
    assert sections["cash_flow"].level is Level.SATISFACTORY  # free cash flow is 11% of revenue
    assert rules.consolidated(sections)[0] in (Level.STRONG, Level.SATISFACTORY)
    assert all(s.trend == "Stable" for key, s in sections.items() if key != "efficiency")


def test_efficiency_and_sector_are_shown_but_never_assessed() -> None:
    sections = rules.assess(contexts(STRONG))
    assert sections["efficiency"].level is Level.NOT_ASSESSED
    assert "not connected" in sections["efficiency"].why
    assert "efficiency" not in rules.CORE  # the policy never reads it


def test_a_distressed_company_is_critical_and_the_consolidated_finding_follows_the_policy() -> None:
    sections = rules.assess(contexts(DISTRESSED))
    for key in rules.CORE:
        assert sections[key].level is Level.WEAK, key  # critical in the framework's words
    level, why = rules.consolidated(sections)
    assert level is Level.WEAK and "4 of the 4" in why
    assert "Negative equity (a shareholders' deficit)" in sections["leverage"].flags
    assert "Current ratio below 1.0" in sections["liquidity"].flags
    assert "Net loss for the period" in sections["profitability"].flags
    assert sections["liquidity"].trend == "Stable"  # critical the year before too


def test_the_framework_thresholds_set_the_levels() -> None:
    assert rules._band_current(2.1) == 3 and rules._band_current(1.6) == 2
    assert rules._band_current(1.2) == 1 and rules._band_current(0.9) == 0
    assert rules._band_quick(1.3) == 3 and rules._band_quick(0.9) == 2
    assert rules._band_quick(0.7) == 1 and rules._band_quick(0.5) == 0
    assert rules._band_ocf_cl(0.6) == 3 and rules._band_ocf_cl(0.4) == 2
    assert rules._band_ocf_cl(0.2) == 1 and rules._band_ocf_cl(0.1) == 0
    assert rules._band_de(0.8) == 3 and rules._band_de(1.4) == 2
    assert rules._band_de(2.0) == 1 and rules._band_de(3.0) == 0
    assert rules._band_cover(5.0) == 3 and rules._band_cover(3.0) == 2
    assert rules._band_cover(2.2) == 1 and rules._band_cover(1.5) == 0
    assert rules._band_fcf(0.25) == 3 and rules._band_fcf(0.15) == 2
    assert rules._band_fcf(0.06) == 1 and rules._band_fcf(-0.01) == 0
    assert rules._band_conversion(10.0, 10.0, 1.0) == 2  # equal to net income is adequate
    assert rules._band_conversion(11.0, 10.0, 1.1) == 3
    assert rules._band_conversion(9.0, 10.0, 0.9) == 1
    assert rules._band_conversion(7.0, 10.0, 0.7) == 0
    assert rules._band_conversion(-1.0, 10.0, None) == 0
    assert rules._band_conversion(None, 10.0, None) is None
    assert rules._worst([3, 1, None]) is Level.NEEDS_ATTENTION  # the worst available metric decides
    assert rules._worst([None]) is Level.NOT_ASSESSED
    for fn in (rules._band_current, rules._band_quick, rules._band_ocf_cl):
        assert fn(None) is None
    for fn in (rules._band_de, rules._band_cover, rules._band_fcf):
        assert fn(None) is None


def test_consolidated_is_weak_only_when_the_core_dimensions_are_critical_together() -> None:
    sections = rules.assess(contexts(STRONG))
    sections["liquidity"].level = Level.WEAK
    sections["profitability"].level = Level.WEAK
    assert (
        rules.consolidated(sections)[0] is Level.SATISFACTORY
    )  # two critical core dimensions are not enough
    sections["leverage"].level = Level.WEAK
    assert rules.consolidated(sections)[0] is Level.WEAK
    sections = rules.assess(contexts(STRONG))
    for key in rules.CORE:
        sections[key].level = Level.STRONG
    assert rules.consolidated(sections)[0] is Level.STRONG
    for key in rules.CORE:
        sections[key].level = Level.NOT_ASSESSED
    assert rules.consolidated(sections)[0] is Level.NOT_ASSESSED


def test_a_narrowing_cushion_is_reported_as_weakening() -> None:
    profile = dict(STRONG)
    profile["LiabilitiesCurrent"] = [250, 250, 400]  # current ratio 2.4 -> 1.75
    sections = rules.assess(contexts(profile))
    assert sections["liquidity"].level is Level.SATISFACTORY
    assert sections["liquidity"].trend == "Weakening"
    assert "Current ratio is lower than the year before" in sections["liquidity"].flags


def test_a_thin_margin_and_a_margin_fall_pull_profitability_down() -> None:
    thin = dict(STRONG)
    thin["NetIncomeLoss"] = [30, 35, 40]  # about 3.7% of revenue
    assert rules.assess(contexts(thin))["profitability"].level is Level.NEEDS_ATTENTION
    fall = dict(STRONG)
    fall["NetIncomeLoss"] = [160, 160, 80]  # 15% down to 7.3%: more than 5 points
    section = rules.assess(contexts(fall))["profitability"]
    assert section.level is Level.NEEDS_ATTENTION
    assert "Net margin fell by more than 5 percentage points" in section.flags


def test_leverage_reads_debt_to_equity_and_interest_cover() -> None:
    profile = dict(STRONG)
    profile["LongTermDebtNoncurrent"] = [600, 600, 700]  # debt to equity 1.17: adequate
    assert rules.assess(contexts(profile))["leverage"].level is Level.SATISFACTORY
    profile["LongTermDebtNoncurrent"] = [1000, 1000, 1300]  # 2.17x equity: concerning
    assert rules.assess(contexts(profile))["leverage"].level is Level.NEEDS_ATTENTION
    profile["LongTermDebtNoncurrent"] = [1000, 1000, 2000]  # 3.3x equity: critical
    section = rules.assess(contexts(profile))["leverage"]
    assert section.level is Level.WEAK and "Debt to equity above 2.5" in section.flags


def test_cash_flow_below_earnings_needs_attention() -> None:
    profile = dict(STRONG)
    profile["NetCashProvidedByUsedInOperatingActivities"] = [140, 150, 112]  # 0.93 x net income
    section = rules.assess(contexts(profile))["cash_flow"]
    assert section.level is Level.NEEDS_ATTENTION
    assert "Cash from operations below net income" in section.flags
    profile["NetCashProvidedByUsedInOperatingActivities"] = [140, 150, 80]  # 0.67 x: critical
    assert rules.assess(contexts(profile))["cash_flow"].level is Level.WEAK


def test_missing_figures_make_a_dimension_not_assessed_never_zero() -> None:
    profile = {
        k: v
        for k, v in STRONG.items()
        if k not in ("LongTermDebtNoncurrent", "LongTermDebtCurrent")
    }
    assert rules.assess(contexts(profile))["leverage"].level is Level.NOT_ASSESSED
    bare: dict[str, list[float | None]] = {"Assets": [1000, 1050, 1100]}
    sections = rules.assess(contexts(bare))
    assert {s.level for s in sections.values()} == {Level.NOT_ASSESSED}


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
    sections["cash_flow"].level = Level.STRONG  # no core dimension is short of strong
    fraction, factors = rules.propose_fraction(
        sections, adverse_search_complete=True, sector_outlook_assessed=True
    )
    assert fraction == Decimal(1) and factors == []

    fraction, factors = rules.propose_fraction(
        sections, adverse_search_complete=False, sector_outlook_assessed=False
    )
    assert fraction == Decimal("0.90")
    assert [f.code for f in factors] == ["missing_information"]


def test_a_concerning_core_dimension_costs_a_share_but_efficiency_never_does() -> None:
    sections = rules.assess(contexts(STRONG))  # cash flow is adequate, efficiency not assessed
    fraction, _ = rules.propose_fraction(
        sections, adverse_search_complete=True, sector_outlook_assessed=True
    )
    assert fraction == Decimal(1)  # adequate is not a reduction
    sections["liquidity"].level = Level.NEEDS_ATTENTION
    fraction, _ = rules.propose_fraction(
        sections, adverse_search_complete=True, sector_outlook_assessed=True
    )
    assert fraction == Decimal("0.95")


def test_critical_dimensions_cost_more_and_the_proposal_never_goes_below_zero() -> None:
    sections = rules.assess(contexts(DISTRESSED))
    fraction, factors = rules.propose_fraction(
        sections, adverse_search_complete=False, sector_outlook_assessed=False
    )
    assert Decimal(0) <= fraction < Decimal("0.50")
    assert {f.code for f in factors} == {"acceptable_not_strong", "missing_information"}


def test_money_helpers_show_currency_and_billions() -> None:
    assert rules.money(9027.0, "USD") == "USD 9.03bn"
    assert rules.money(-369.0, "USD") == "-USD 369m"
    assert rules.money(1085.0, "CAD") == "CAD 1.09bn"
    assert rules.money(0.75, "CAD") == "CAD 0.75m"
    assert rules.money(1.0, "CAD") == "CAD 1.00m"
    assert rules.money(None) == "not available"


def test_leverage_text_keeps_currency_codes_and_ebitda_in_capitals() -> None:
    """Found on the live Nike case: the text read 'net debt is 0.44x ebitda' and 'Equity is -usd 50m'."""
    strong = rules.assess(contexts(STRONG))["leverage"].why
    assert "EBITDA" in strong and "ebitda" not in strong and strong[0].isupper()
    distressed = rules.assess(contexts(DISTRESSED))["leverage"].why
    assert "-USD 50m" in distressed and "usd" not in distressed
    assert "EBITDA" in distressed and distressed.endswith(".")
