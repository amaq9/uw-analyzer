#!/usr/bin/env python3
"""Financial ratio calculator for the five-area credit review.

Input: a JSON object of figures (same currency and unit). Any figure not supplied
makes the dependent ratios `null` (not calculable); nothing is defaulted to zero and
negative values are preserved.

Usage: python calculate_ratios.py figures.json
"""

import json
import sys
from typing import Any

Figures = dict[str, float | None]


def _get(f: Figures, key: str) -> float | None:
    value = f.get(key)
    return None if value is None else float(value)


def ratio(num: float | None, den: float | None) -> float | None:
    """num / den, or None when either is missing or the denominator is not positive."""
    if num is None or den is None or den <= 0:
        return None
    return num / den


def _minus(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


def balance_sheet(f: Figures) -> dict[str, float | None]:
    equity, assets = _get(f, "total_equity"), _get(f, "total_assets")
    intangibles = None
    if _get(f, "goodwill") is not None or _get(f, "intangibles") is not None:
        intangibles = (_get(f, "goodwill") or 0.0) + (_get(f, "intangibles") or 0.0)
    return {
        "equity": equity,  # negative = shareholders' deficit
        "equity_to_assets": ratio(equity, assets),
        "goodwill_and_intangibles_to_assets": ratio(intangibles, assets),
        # Only meaningful while equity is positive; with a deficit, read the raw figures.
        "goodwill_and_intangibles_to_equity": ratio(intangibles, equity),
    }


def liquidity(f: Figures) -> dict[str, float | None]:
    ca, cl = _get(f, "current_assets"), _get(f, "current_liabilities")
    inv, cash = _get(f, "inventory"), _get(f, "cash")
    return {
        "current_ratio": ratio(ca, cl),
        "quick_ratio": ratio(_minus(ca, inv), cl),
        "cash_ratio": ratio(cash, cl),
        "working_capital": _minus(ca, cl),
        "ocf_to_current_liabilities": ratio(_get(f, "ocf"), cl),
        "cash_plus_undrawn_less_debt_due_12m": _minus(
            None if cash is None else cash + (_get(f, "undrawn_facilities") or 0.0),
            _get(f, "debt_due_12m"),
        ),
    }


def gearing(f: Figures) -> dict[str, float | None]:
    debt, cash = _get(f, "financial_debt"), _get(f, "cash")
    leases = _get(f, "lease_liabilities")
    total_debt = None if debt is None else debt + (leases or 0.0)
    net_debt = _minus(total_debt, cash)  # negative = net cash
    equity, ebitda, ebit, interest = (
        _get(f, "total_equity"),
        _get(f, "ebitda"),
        _get(f, "ebit"),
        _get(f, "interest_expense"),
    )
    return {
        "total_debt_incl_leases": total_debt,
        "net_debt": net_debt,
        "debt_to_equity": ratio(total_debt, equity),
        "net_debt_to_ebitda": ratio(net_debt, ebitda) if net_debt is not None else None,
        "interest_cover": (
            None if ebit is None or interest is None or interest <= 0 else ebit / interest
        ),
    }


def receivables(f: Figures) -> dict[str, float | None]:
    ar, revenue, prior_ar = _get(f, "receivables"), _get(f, "revenue"), _get(f, "prior_receivables")
    days = _get(f, "days_in_period") or 365.0
    return {
        "receivables": ar,
        "dso_days": None if ar is None or revenue is None or revenue <= 0 else ar / revenue * days,
        "cash_absorbed_by_receivables": _minus(ar, prior_ar),
        "allowance_to_receivables": ratio(_get(f, "allowance_for_credit_losses"), ar),
        "aging_schedule_disclosed": None,  # never inferred: state "not disclosed" unless the filing has one
    }


def cash_flow(f: Figures) -> dict[str, float | None]:
    ocf, capex = _get(f, "ocf"), _get(f, "capex")
    fcf = _minus(ocf, None if capex is None else abs(capex))
    distributions = None
    if _get(f, "dividends") is not None or _get(f, "buybacks") is not None:
        distributions = abs(_get(f, "dividends") or 0.0) + abs(_get(f, "buybacks") or 0.0)
    ni = _get(f, "net_income")
    return {
        "free_cash_flow": fcf,
        "fcf_after_distributions": _minus(fcf, distributions),
        "ocf_to_net_income": None if ocf is None or ni is None or ni <= 0 else ocf / ni,
        "net_change_in_cash": _get(f, "net_change_in_cash"),
    }


def compute(f: Figures) -> dict[str, dict[str, Any]]:
    return {
        "balance_sheet": balance_sheet(f),
        "liquidity": liquidity(f),
        "gearing": gearing(f),
        "receivables": receivables(f),
        "cash_flow": cash_flow(f),
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: calculate_ratios.py figures.json")
    with open(sys.argv[1], encoding="utf-8") as fh:
        print(json.dumps(compute(json.load(fh)), indent=2))
