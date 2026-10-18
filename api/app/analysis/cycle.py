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

from app.analysis.formats import days, pct
from app.analysis.narrative import FINDING, Measure, summarise
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

    rating = rate_cycle(sets, figs)
    return CashCycle(
        periods=periods[: len(sets)],
        rows=rows,
        summary=_summary(sets),
        notes=notes,
        status=rating["status"],
        finding=rating["finding"],
        trend=rating["trend"],
        standing=rating["standing"],
        flags=rating["flags"],
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


# --- the rating: same four words as the financial dimensions, judged on how the cycle moved ----------------

_LEVEL = {3: "STRONG", 2: "SATISFACTORY", 1: "NEEDS_ATTENTION", 0: "WEAK"}
_RANK = {"WEAK": 0, "NEEDS_ATTENTION": 1, "SATISFACTORY": 2, "STRONG": 3}
_CYCLE_REFERENCE = (
    "no longer (a day more at most) is strong; up to 5 days longer adequate; more than 5 days longer "
    "concerning, more than 15 days critical"
)


def _band_days(change: float) -> int:
    """How a lengthening (or shortening) in days is judged. More days tie up more cash."""
    return 3 if change <= 1 else 2 if change <= 5 else 1 if change <= 15 else 0


def _band_payables(change: float) -> int | None:
    """Paying much later may mean suppliers are being stretched; much sooner, that suppliers tightened terms."""
    return 1 if change > 15 or change < -10 else None


def _measures(now: dict[str, Any], before: dict[str, Any]) -> list[Measure] | None:
    if now["ccc"] is None or before["ccc"] is None:
        return None
    ch = {
        k: None if now[k] is None or before[k] is None else now[k] - before[k]
        for k in ("dso", "dio", "dpo", "ccc")
    }
    out = [
        Measure(
            "Change in the cash conversion cycle",
            ch["ccc"],
            None,
            "days_change",
            None if ch["ccc"] is None else _band_days(ch["ccc"]),
            _CYCLE_REFERENCE,
            False,
        ),
        Measure(
            "Change in days sales outstanding",
            ch["dso"],
            None,
            "days_change",
            None if ch["dso"] is None else _band_days(ch["dso"]),
            _CYCLE_REFERENCE,
            False,
        ),
    ]
    if not now["no_inventory"] and ch["dio"] is not None:
        out.append(
            Measure(
                "Change in days inventory outstanding",
                ch["dio"],
                None,
                "days_change",
                _band_days(ch["dio"]),
                _CYCLE_REFERENCE,
                False,
            )
        )
    if ch["dpo"] is not None:
        out.append(
            Measure(
                "Change in days payables outstanding",
                ch["dpo"],
                None,
                "days_change",
                _band_payables(ch["dpo"]),
                "a change of more than 15 days longer or 10 days shorter is a warning",
                True,
            )
        )
    out += [
        Measure(
            "Cash conversion cycle",
            now["ccc"],
            before["ccc"],
            "days",
            None,
            "shown for context",
            False,
        ),
        Measure(
            "Days sales outstanding",
            now["dso"],
            before["dso"],
            "days",
            None,
            "shown for context",
            False,
        ),
    ]
    if not now["no_inventory"]:
        out.append(
            Measure(
                "Days inventory outstanding",
                now["dio"],
                before["dio"],
                "days",
                None,
                "shown for context",
                False,
            )
        )
    out.append(
        Measure(
            "Days payables outstanding",
            now["dpo"],
            before["dpo"],
            "days",
            None,
            "shown for context",
            True,
        )
    )
    return out


def _level(measures: list[Measure]) -> str | None:
    banded = [m.band for m in measures if m.band is not None and m.value is not None]
    return _LEVEL[min(banded)] if banded else None


def _recommendations(
    measures: list[Measure], figs: list[Figures], sets: list[dict[str, Any]]
) -> list[str]:
    by = {m.label: m for m in measures}
    recs: list[str] = []
    dso = by.get("Change in days sales outstanding")
    if dso is not None and dso.band is not None and dso.band <= 1:
        cur, prev = figs[0], figs[1] if len(figs) > 1 else {}
        rec_now, rec_before = cur.get("receivables"), prev.get("receivables")
        rev_now, rev_before = cur.get("revenue"), prev.get("revenue")
        extra = ""
        if rec_now and rec_before and rev_now and rev_before and rec_before > 0 and rev_before > 0:
            extra = f" (receivables {pct(rec_now / rec_before - 1)} against revenue {pct(rev_now / rev_before - 1)})"
        again = ""
        three = [sets[i]["dso"] for i in range(3)] if len(sets) > 2 else []
        if three and None not in three and three[1] - three[2] > 5:
            again = (
                " Days sales outstanding has lengthened two years running "
                f"({three[2]:.1f} to {three[1]:.1f} to {three[0]:.1f} days)."
            )
        recs.append(
            "Customers are paying more slowly"
            + extra
            + "."
            + again
            + " Ask for the receivables ageing and the largest overdue balances, and whether payment terms "
            "were extended or sales were pulled forward."
        )
    dio = by.get("Change in days inventory outstanding")
    if dio is not None and dio.band is not None and dio.band <= 1:
        recs.append(
            "Stock is turning more slowly. Ask what is behind the build-up (slow-moving or aged stock) and whether write-downs are needed."
        )
    dpo = by.get("Change in days payables outstanding")
    if dpo is not None and dpo.band == 1 and dpo.value is not None:
        recs.append(
            "The company is paying suppliers much later. Ask whether it is stretching suppliers to fund working capital."
            if dpo.value > 0
            else "The company is paying suppliers much sooner. Ask whether suppliers have tightened their terms."
        )
    ccc = by.get("Change in the cash conversion cycle")
    if not recs and ccc is not None and ccc.band is not None and ccc.band <= 1:
        recs.append("Ask what has lengthened the cycle and whether it is temporary.")
    if recs:
        recs.append(
            "Check the next period: a cycle that keeps lengthening ties up cash and strains liquidity."
        )
    return recs


def rate_cycle(sets: list[dict[str, Any]], figs: list[Figures]) -> dict[str, Any]:
    """Status, finding, trend and the paragraph (why it stands there, and what to do) for the cycle."""
    none = {
        "status": "NOT_ASSESSED",
        "finding": "Not assessed",
        "trend": "No earlier year to compare",
        "flags": [],
        "standing": (
            "The cycle is not rated: it needs the cycle for this period and the period before, and "
            "receivables, trade payables and cost of sales for both."
        ),
    }
    if len(sets) < 2:
        return none
    measures = _measures(sets[0], sets[1])
    level = _level(measures) if measures else None
    if not measures or level is None:
        return none
    earlier_measures = _measures(sets[1], sets[2]) if len(sets) > 2 else None
    earlier = _level(earlier_measures) if earlier_measures else None
    trend = "No earlier year to compare"
    if earlier is not None:
        delta = _RANK[level] - _RANK[earlier]
        trend = "Improving" if delta > 0 else "Weakening" if delta < 0 else "Stable"
    text = summarise(
        title="The cash conversion cycle",
        level=level,
        trend=trend,
        earlier_level=earlier,
        measures=measures,
        currency="USD",
        cut_percent=None,
        core=False,
    )
    recs = _recommendations(measures, figs, sets)
    if recs:
        text += " What to do: " + " ".join(recs)
    text += " This is context only: it does not change the recommended amount."
    flags = [
        f"{m.label}: {m.show(m.value, 'USD')}"
        for m in measures
        if m.band is not None and m.band <= 1 and m.value is not None
    ]
    return {
        "status": _STATUS_WORD[level],
        "finding": FINDING[level],
        "trend": trend,
        "flags": flags[:6],
        "standing": text[:1800],
    }


_STATUS_WORD = {
    "STRONG": "OK",
    "SATISFACTORY": "OK",
    "NEEDS_ATTENTION": "WEAK",
    "WEAK": "DISTRESSED",
}
