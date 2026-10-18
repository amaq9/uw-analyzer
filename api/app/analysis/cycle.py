"""The cash conversion cycle: how many days cash is tied up between paying suppliers and collecting from customers.

    DSO = receivables / revenue x 365           (days sales outstanding: how long customers take to pay)
    DIO = inventory / cost of sales x 365       (days inventory outstanding: how long stock sits)
    DPO = trade payables / cost of sales x 365  (days payables outstanding: how long the company takes to pay)
    CCC = DSO + DIO - DPO

Year-end balances are used for every period so the periods compare like for like. Nothing is estimated: a
figure that cannot be calculated is left blank and the reason is stated. A company with no inventory (a
services business, say) has no DIO: it is shown as "No inventory reported" and the cycle is DSO less DPO.
It is context for the underwriter and sets no finding and no amount."""

from typing import Any

from app.analysis.formats import days
from app.analysis.ratios import Figures
from app.recommendation.analysis_report import CashCycle, CycleRow

NO_INVENTORY = "No inventory reported"


def _per(balance: float | None, flow: float | None, period_days: float) -> float | None:
    if balance is None or flow is None or flow <= 0 or balance < 0:
        return None
    return balance / flow * period_days


def period_figures(f: Figures) -> dict[str, Any]:
    """DSO, DIO, DPO and CCC for one period. `no_inventory` is true when the company reports none."""
    period_days = f.get("days_in_period") or 365.0
    revenue, cost = f.get("revenue"), f.get("cost_of_revenue")
    inventory = f.get("inventory")
    no_inventory = inventory is None or inventory == 0
    dso = _per(f.get("receivables"), revenue, period_days)
    dio = None if no_inventory else _per(inventory, cost, period_days)
    dpo = _per(f.get("payables"), cost, period_days)
    ccc = None
    if dso is not None and dpo is not None and (dio is not None or no_inventory):
        ccc = dso + (dio or 0.0) - dpo
    return {"dso": dso, "dio": dio, "dpo": dpo, "ccc": ccc, "no_inventory": no_inventory}


def _show(value: float | None, key: str, no_inventory: bool, cost_missing: bool) -> str:
    if key == "dio" and no_inventory:
        return NO_INVENTORY
    if value is not None:
        return days(value)
    if key in ("dio", "dpo") and cost_missing:
        return "not calculable (no cost of sales)"
    return "not available"


def _movement(key: str, now: float | None, before: float | None) -> tuple[str, str]:
    """The change in days against the year before, in words, and whether it helps cash."""
    if now is None or before is None:
        return "No comparison available", "unknown"
    delta = now - before
    if abs(delta) < 0.05:
        return "Unchanged", "same"
    longer = delta > 0
    word = f"{'Longer' if longer else 'Shorter'} by {abs(delta):.1f} days"
    # More days to collect, more days of stock and a longer cycle tie up more cash. A longer payment period holds
    # cash for longer, though it can also mean suppliers are being stretched.
    helps = (not longer) if key in ("dso", "dio", "ccc") else longer
    note = {
        "dso": "slower collection" if longer else "faster collection",
        "dio": "slower stock turnover" if longer else "faster stock turnover",
        "dpo": "paying suppliers later" if longer else "paying suppliers sooner",
        "ccc": "more cash tied up" if longer else "less cash tied up",
    }[key]
    return f"{word} ({note})", "better" if helps else "worse"


_LABELS = {
    "dso": "Days sales outstanding (DSO)",
    "dio": "Days inventory outstanding (DIO)",
    "dpo": "Days payables outstanding (DPO)",
    "ccc": "Cash conversion cycle (CCC = DSO + DIO - DPO)",
}


def build_cash_cycle(
    figs: list[Figures], periods: list[str], definitions: list[str]
) -> CashCycle | None:
    """None when there is nothing to calculate (no revenue and no balances at all)."""
    sets = [period_figures(f) for f in figs]
    if not any(s[k] is not None for s in sets for k in ("dso", "dio", "dpo")):
        return None
    cost_missing = [f.get("cost_of_revenue") is None for f in figs]
    rows: list[CycleRow] = []
    for key in ("dso", "dio", "dpo", "ccc"):
        shown = [_show(s[key], key, s["no_inventory"], cost_missing[i]) for i, s in enumerate(sets)]
        now, before = sets[0][key], sets[1][key] if len(sets) > 1 else None
        movement, direction = (
            ("No earlier year to compare", "unknown")
            if len(sets) < 2
            else _movement(key, now, before)
        )
        if key == "dio" and sets[0]["no_inventory"]:
            movement, direction = "Not applicable: no inventory", "unknown"
        rows.append(
            CycleRow(
                key=key,
                label=_LABELS[key],
                current=shown[0],
                prior=shown[1] if len(shown) > 1 else None,
                earlier=shown[2] if len(shown) > 2 else None,
                movement=movement,
                direction=direction,  # type: ignore[arg-type]
            )
        )

    notes: list[str] = []
    if sets[0]["no_inventory"]:
        notes.append(
            "The company reports no inventory, so days inventory outstanding is left blank and the cycle is "
            "days sales outstanding less days payables outstanding."
        )
    if any("finished goods only" in d for d in definitions):
        notes.append(
            "Inventory is taken from the finished-goods figure (total inventory is not tagged). If the company "
            "also holds raw materials or work in progress, days inventory outstanding is understated."
        )
    if any("revenue less gross profit" in d for d in definitions):
        notes.append("Cost of sales is revenue less gross profit (cost of sales is not tagged).")
    if cost_missing[0] and not sets[0]["no_inventory"]:
        notes.append(
            "Cost of sales is not available, so days inventory and payables cannot be calculated."
        )
    if sets[0]["dpo"] is None and not cost_missing[0]:
        notes.append(
            "Trade payables were not available, so days payables outstanding cannot be calculated."
        )
    if sets[0]["dso"] is None:
        notes.append(
            "Receivables or revenue were not available, so days sales outstanding cannot be calculated."
        )

    return CashCycle(
        periods=periods[: len(sets)],
        rows=rows,
        summary=_summary(sets),
        notes=notes,
    )


def _summary(sets: list[dict[str, Any]]) -> str:
    cur = sets[0]
    before = sets[1] if len(sets) > 1 else None

    def part(key: str, word: str) -> str:
        v = cur[key]
        if key == "dio" and cur["no_inventory"]:
            return "holds no inventory"
        if v is None:
            return f"{word} could not be calculated"
        was = ""
        if before is not None and before[key] is not None:
            was = f" (was {days(before[key])})"
        return {
            "dso": f"collects from customers in {days(v)}{was}",
            "dio": f"holds inventory for {days(v)}{was}",
            "dpo": f"pays suppliers in {days(v)}{was}",
        }[key]

    text = (
        "The company "
        + part("dso", "collection time")
        + ", "
        + part("dio", "inventory days")
        + " and "
        + part("dpo", "payment time")
        + "."
    )
    if cur["ccc"] is None:
        return (
            text + " The cash conversion cycle could not be calculated from the figures available."
        )
    text += f" Cash is therefore tied up for {days(cur['ccc'])} between paying suppliers and collecting from customers"
    if before is not None and before["ccc"] is not None:
        delta = cur["ccc"] - before["ccc"]
        if abs(delta) < 0.05:
            text += f", unchanged from the year before ({days(before['ccc'])})."
        else:
            contrib = {
                "collecting from customers": (cur["dso"] or 0) - (before["dso"] or 0)
                if cur["dso"] is not None and before["dso"] is not None
                else 0.0,
                "holding inventory": (cur["dio"] or 0) - (before["dio"] or 0)
                if cur["dio"] is not None and before["dio"] is not None
                else 0.0,
                "paying suppliers": -((cur["dpo"] or 0) - (before["dpo"] or 0))
                if cur["dpo"] is not None and before["dpo"] is not None
                else 0.0,
            }
            main = max(contrib, key=lambda k: abs(contrib[k]))
            text += (
                f", {'longer' if delta > 0 else 'shorter'} than the year before ({days(before['ccc'])}) by "
                f"{abs(delta):.1f} days. "
                + (
                    f"The biggest part of the change is {main} ({contrib[main]:+.1f} days on the cycle)."
                    if contrib[main]
                    else ""
                )
            )
            text = text.rstrip()
    else:
        text += "."
    return text
