"""The per-period figures behind the five analyst dimensions (liquidity, profitability, leverage,
cash flow, efficiency and sector), computed once and used both by the section rules (which set the
findings the recommendation policy reads) and by the Step 1 report (which shows them).

Nothing is estimated: a figure that cannot be calculated is None and is shown as "not disclosed".
Amounts are in millions of the case currency."""

from typing import Any

from app.analysis.ratios import Figures

Metrics = dict[str, float | None]


def div(num: float | None, den: float | None) -> float | None:
    """num / den, or None when either is missing or the denominator is not positive."""
    if num is None or den is None or den <= 0:
        return None
    return num / den


def _avg(a: float | None, b: float | None) -> float | None:
    """Average of two periods; with no earlier period, the latest figure alone."""
    return a if b is None else None if a is None else (a + b) / 2


def dimension_metrics(
    ratios: dict[str, dict[str, Any]], f: Figures, prior: Figures | None
) -> dict[str, Metrics]:
    """Every metric of the five dimensions for one period. `prior` is the period before, if any."""
    liq, bs, gear = ratios["liquidity"], ratios["balance_sheet"], ratios["gearing"]
    cf, rec = ratios["cash_flow"], ratios["receivables"]
    rev, ni = f.get("revenue"), f.get("net_income")
    ebit = f.get("operating_income") if f.get("operating_income") is not None else f.get("ebit")
    ocf, fcf = cf["operating_cash_flow"], cf["free_cash_flow"]
    prior_rev = prior.get("revenue") if prior else None
    assets = _avg(f.get("total_assets"), prior.get("total_assets") if prior else None)
    equity = _avg(f.get("total_equity"), prior.get("total_equity") if prior else None)
    capex, dep = f.get("capex"), f.get("depreciation_amortisation")
    gross_profit = f.get("gross_profit")
    cogs = None if rev is None or gross_profit is None else rev - gross_profit
    avg_inventory = _avg(f.get("inventory"), prior.get("inventory") if prior else None)
    return {
        "liquidity": {
            "current_ratio": liq["current_ratio"],
            "quick_ratio": liq["quick_ratio"],
            "cash_ratio": liq["cash_ratio"],
            "working_capital": liq["working_capital"],
            "cash_less_debt_due_12m": liq["cash_less_debt_due_12m"],
            "ocf_to_current_liabilities": div(ocf, f.get("current_liabilities")),
        },
        "profitability": {
            "revenue": rev,
            "growth": None
            if rev is None or not prior_rev or prior_rev <= 0
            else rev / prior_rev - 1,
            "gross_margin": div(gross_profit, rev),
            "operating_margin": None if ebit is None or rev is None or rev <= 0 else ebit / rev,
            "ebitda_margin": div(f.get("ebitda"), rev),
            "net_margin": None if ni is None or rev is None or rev <= 0 else ni / rev,
            "return_on_assets": None
            if ni is None or assets is None or assets <= 0
            else ni / assets,
            "return_on_equity": None
            if ni is None or equity is None or equity <= 0
            else ni / equity,
        },
        "leverage": {
            "debt_to_equity": gear["debt_to_equity"],
            "debt_to_assets": div(gear["total_debt_incl_leases"], f.get("total_assets")),
            "equity_ratio": bs["equity_to_assets"],
            "interest_cover": gear["interest_cover"],
            "net_debt_to_ebitda": gear["net_debt_to_ebitda"],
            "financial_debt": gear["financial_debt"],
            "net_debt": gear["net_debt"],
            "equity": bs["equity"],
        },
        "cash_flow": {
            "operating_cash_flow": ocf,
            "free_cash_flow": fcf,
            "fcf_margin": None if fcf is None or rev is None or rev <= 0 else fcf / rev,
            "ocf_to_net_income": cf["ocf_to_net_income"],
            "capex_to_depreciation": div(None if capex is None else abs(capex), dep),
            "distributions": cf["distributions"],
            "fcf_after_distributions": cf["fcf_after_distributions"],
            "net_change_in_cash": cf["net_change_in_cash"],
        },
        "efficiency": {
            "asset_turnover": div(rev, assets),
            "dso_days": rec["dso_days"],
            "inventory_turnover": div(cogs, avg_inventory),
        },
    }
