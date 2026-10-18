"""Build the written-up analysis (Step 1) from the analyzer's figures and findings.

Pure and deterministic: the same figures give the same report. Nothing here decides anything. It lays
out the five areas of the financial-statement-assessment skill with their figures, runs the skill's
red-flag checklist as prompts for attention, and closes with strengths, weaknesses, what to watch and
what is not known."""

from typing import Any, Literal

from app.analysis.assess import CORE, Level, Section, money, pct, times
from app.analysis.ratios import Figures
from app.recommendation.analysis_report import (
    AnalysisReport,
    AreaReport,
    Basis,
    FlagCheck,
    Metric,
    OtherCheck,
    Status,
    StressRow,
)

STATUS_OF: dict[Level, Status] = {
    Level.STRONG: "OK",
    Level.SATISFACTORY: "OK",
    Level.NEEDS_ATTENTION: "WEAK",
    Level.WEAK: "DISTRESSED",
    Level.NOT_ASSESSED: "NOT_ASSESSED",
}


STATUS_WORD: dict[Status, str] = {
    "OK": "OK",
    "WEAK": "weak",
    "DISTRESSED": "distressed",
    "NOT_ASSESSED": "not assessed",
}


def finding_word(level: Level) -> str:
    return level.value.replace("_", " ").capitalize()


# (label, where it lives, key, how to show it). "r" = a computed ratio, "f" = a supplied figure.
_SPECS: dict[str, list[tuple[str, str, str, str]]] = {
    "balance_sheet": [
        ("Total assets", "f", "total_assets", "money"),
        ("Total equity", "r", "equity", "money"),
        ("Equity as a share of assets", "r", "equity_to_assets", "pct"),
        ("Goodwill and intangibles", "r", "goodwill_and_intangibles", "money"),
        (
            "Goodwill and intangibles as a share of assets",
            "r",
            "goodwill_and_intangibles_to_assets",
            "pct",
        ),
        (
            "Goodwill and intangibles as a share of equity",
            "r",
            "goodwill_and_intangibles_to_equity",
            "pct",
        ),
    ],
    "liquidity": [
        ("Current ratio", "r", "current_ratio", "times"),
        ("Quick ratio", "r", "quick_ratio", "times"),
        ("Cash ratio", "r", "cash_ratio", "times"),
        ("Working capital", "r", "working_capital", "money"),
        ("Cash less debt due within 12 months", "r", "cash_less_debt_due_12m", "money"),
    ],
    "gearing": [
        ("Financial debt", "r", "financial_debt", "money"),
        ("Total debt including leases", "r", "total_debt_incl_leases", "money"),
        ("Net debt (negative is net cash)", "r", "net_debt", "money"),
        ("Debt to equity", "r", "debt_to_equity", "times"),
        ("Net debt to EBITDA", "r", "net_debt_to_ebitda", "times"),
        ("Interest cover (EBIT over interest)", "r", "interest_cover", "times"),
    ],
    "receivables": [
        ("Receivables", "r", "receivables", "money"),
        ("Days of revenue in receivables", "r", "dso_days", "days"),
        ("Cash absorbed by receivables in the year", "r", "cash_absorbed_by_receivables", "money"),
        (
            "Allowance for credit losses as a share of receivables",
            "r",
            "allowance_to_receivables",
            "pct",
        ),
    ],
    "cash_flow": [
        ("Cash from operations", "r", "operating_cash_flow", "money"),
        ("Free cash flow (after capital spending)", "r", "free_cash_flow", "money"),
        ("Dividends and buybacks", "r", "distributions", "money"),
        ("Free cash flow after dividends and buybacks", "r", "fcf_after_distributions", "money"),
        ("Cash from operations as a multiple of net income", "r", "ocf_to_net_income", "times"),
        ("Net change in cash", "r", "net_change_in_cash", "money"),
    ],
}


def _show(kind: str, value: float | None, currency: str) -> str:
    if value is None:
        return "Not disclosed"
    if kind == "money":
        return money(value, currency)
    if kind == "pct":
        return pct(value)
    if kind == "times":
        return times(value)
    return f"{value:.1f} days"


def _change(cur: float | None, prior: float | None) -> Literal["up", "down", "flat", "unknown"]:
    if cur is None or prior is None:
        return "unknown"
    span = max(abs(cur), abs(prior), 1e-9)
    if abs(cur - prior) / span < 0.005:
        return "flat"
    return "up" if cur > prior else "down"


def _row(label: str, kind: str, values: list[float | None], currency: str) -> Metric | None:
    """One figure across up to three periods (newest first). Skipped when nothing is disclosed."""
    if all(v is None for v in values):
        return None
    padded = values + [None] * (3 - len(values))
    return Metric(
        label=label,
        current=_show(kind, padded[0], currency),
        prior=_show(kind, padded[1], currency) if len(values) > 1 else "No earlier year",
        earlier=_show(kind, padded[2], currency) if len(values) > 2 else "No earlier year",
        change=_change(padded[0], padded[1]),
    )


def _metrics(
    key: str,
    ratio_sets: list[dict[str, dict[str, Any]]],
    figure_sets: list[Figures],
    currency: str,
) -> list[Metric]:
    out: list[Metric] = []
    for label, where, name, kind in _SPECS[key]:
        values = [
            figure_sets[i].get(name) if where == "f" else ratio_sets[i][key].get(name)
            for i in range(len(ratio_sets))
        ]
        row = _row(label, kind, values, currency)
        if row is not None:
            out.append(row)
    return out


def _flag(text: str, triggered: bool | None, yes: str, no: str, unknown: str) -> FlagCheck:
    if triggered is None:
        return FlagCheck(text=text, state="NOT_ASSESSABLE", detail=unknown)
    return FlagCheck(
        text=text, state="TRIGGERED" if triggered else "CLEAR", detail=yes if triggered else no
    )


def red_flag_checklist(
    ratios: dict[str, dict[str, Any]],
    figures: Figures,
    prior_figures: Figures | None,
    currency: str,
) -> list[FlagCheck]:
    """The skill's checklist, item by item. TRIGGERED means look closer, not that something failed."""
    liq, bs, gear = ratios["liquidity"], ratios["balance_sheet"], ratios["gearing"]
    cf = ratios["cash_flow"]
    cr, quick, buffer = liq["current_ratio"], liq["quick_ratio"], liq["cash_less_debt_due_12m"]
    eq, cover, nd = bs["equity"], gear["interest_cover"], gear["net_debt_to_ebitda"]
    ocf, ni = cf["operating_cash_flow"], figures.get("net_income")
    after = cf["fcf_after_distributions"]

    def liq_state() -> bool | None:
        if cr is None and quick is None:
            return None
        return (cr is not None and cr < 1.0) or (quick is not None and quick < 0.6)

    cover_state: bool | None
    ebit, interest = figures.get("ebit"), figures.get("interest_expense")
    if cover is not None:
        cover_state = cover < 2.0
    elif ebit is not None and interest is not None and interest > 0:
        cover_state = ebit < interest
    else:
        cover_state = None

    ocf_state: bool | None = None
    if ocf is not None:
        ocf_state = ocf < 0 or (ni is not None and ni > 0 and ocf < ni)

    rec_growth = rev_growth = None
    cur_ar, prev_ar = figures.get("receivables"), figures.get("prior_receivables")
    if cur_ar is not None and prev_ar not in (None, 0) and prev_ar and prev_ar > 0:
        rec_growth = cur_ar / prev_ar - 1
    cur_rev = figures.get("revenue")
    prev_rev = prior_figures.get("revenue") if prior_figures else None
    if cur_rev is not None and prev_rev and prev_rev > 0:
        rev_growth = cur_rev / prev_rev - 1
    rec_state = None if rec_growth is None or rev_growth is None else rec_growth > rev_growth + 0.10

    intang_e = bs["goodwill_and_intangibles_to_equity"]
    return [
        _flag(
            "Current ratio below 1.0, or quick ratio below 0.6",
            liq_state(),
            f"Current ratio {times(cr)}, quick ratio {times(quick)}.",
            f"Current ratio {times(cr)}, quick ratio {times(quick)}.",
            "Current assets or liabilities were not available.",
        ),
        _flag(
            "Negative shareholders' equity",
            None if eq is None else eq <= 0,
            f"Equity is {money(eq, currency)}.",
            f"Equity is {money(eq, currency)}.",
            "Equity was not available.",
        ),
        _flag(
            "Interest cover below 2.0x, or EBIT below interest",
            cover_state,
            f"Interest cover is {times(cover)}.",
            f"Interest cover is {times(cover)}.",
            "EBIT or interest expense was not available.",
        ),
        _flag(
            "Net debt to EBITDA above 3.0x",
            None if nd is None and gear["net_debt"] is None else (nd is not None and nd > 3.0),
            f"Net debt is {times(nd)} EBITDA.",
            "Net debt to EBITDA is "
            + (times(nd) if nd is not None else "not meaningful (net cash or no EBITDA)")
            + ".",
            "Debt or EBITDA was not available.",
        ),
        _flag(
            "Cash from operations below net income, or negative",
            ocf_state,
            f"Cash from operations {money(ocf, currency)} against net income {money(ni, currency)}.",
            f"Cash from operations {money(ocf, currency)} against net income {money(ni, currency)}.",
            "Cash from operations was not available.",
        ),
        _flag(
            "Free cash flow not covering dividends and buybacks",
            None if after is None else after < 0,
            f"Free cash flow after dividends and buybacks is {money(after, currency)}.",
            f"Free cash flow after dividends and buybacks is {money(after, currency)}.",
            "Free cash flow or distributions were not available.",
        ),
        _flag(
            "Debt due within 12 months that cash does not cover",
            None if buffer is None else buffer < 0,
            f"Cash less debt due within 12 months is {money(buffer, currency)}. Undrawn committed facilities are not in the figures.",
            f"Cash less debt due within 12 months is {money(buffer, currency)}. Undrawn committed facilities are not in the figures.",
            "Debt due within 12 months was not available.",
        ),
        _flag(
            "Receivables growing faster than revenue",
            rec_state,
            f"Receivables changed {pct(rec_growth)} against revenue {pct(rev_growth)}.",
            f"Receivables changed {pct(rec_growth)} against revenue {pct(rev_growth)}.",
            "A prior year or revenue was not available to compare.",
        ),
        _flag(
            "Goodwill and intangibles large relative to equity",
            None if intang_e is None else intang_e > 1.0,
            f"Goodwill and intangibles are {pct(intang_e)} of equity.",
            f"Goodwill and intangibles are {pct(intang_e)} of equity.",
            "Goodwill, intangibles or equity were not available.",
        ),
        FlagCheck(
            text="Going-concern language, covenant breach, auditor change or qualification",
            state="NOT_ASSESSABLE",
            detail="Needs the text of the statements, notes and auditor's report, which the analyzer does not read.",
        ),
    ]


def _watch(
    sections: dict[str, Section],
    ratios: dict[str, dict[str, Any]],
    checks: list[FlagCheck],
) -> list[str]:
    watch = [f"{c.text}: {c.detail}" for c in checks if c.state == "TRIGGERED"]
    for sec in sections.values():
        if sec.trend == "Weakening":
            watch.append(f"{sec.title} is weaker than the year before.")
    liq, gear = ratios["liquidity"], ratios["gearing"]
    cr = liq["current_ratio"]
    if cr is not None and 1.0 <= cr < 1.5:
        watch.append(f"Current ratio is {times(cr)}: close enough to 1.0 to watch each period.")
    cover = gear["interest_cover"]
    if cover is not None and 2.0 <= cover < 3.0:
        watch.append(
            f"Interest cover is {times(cover)}: a small fall in earnings would bring it under 2.0x."
        )
    nd = gear["net_debt_to_ebitda"]
    if nd is not None and 2.0 <= nd <= 3.0:
        watch.append(f"Net debt is {times(nd)} EBITDA: close to the 3.0x line.")
    watch.append(
        "Debt maturities, covenant headroom and undrawn committed facilities are not in the figures."
    )
    return watch


def _div(num: float | None, den: float | None) -> float | None:
    if num is None or den is None or den <= 0:
        return None
    return num / den


def _avg(a: float | None, b: float | None) -> float | None:
    return a if b is None else None if a is None else (a + b) / 2


def _year_profit(figs: list[Figures], i: int) -> dict[str, float | None]:
    """Margins and returns for period i (newest first). Averages use the period before when there is one."""
    f = figs[i]
    prior = figs[i + 1] if i + 1 < len(figs) else None
    rev = f.get("revenue")
    ebit = f.get("operating_income") if f.get("operating_income") is not None else f.get("ebit")
    ni = f.get("net_income")
    assets = _avg(f.get("total_assets"), prior.get("total_assets") if prior else None)
    equity = _avg(f.get("total_equity"), prior.get("total_equity") if prior else None)
    prior_rev = prior.get("revenue") if prior else None
    return {
        "revenue": rev,
        "growth": None if rev is None or not prior_rev or prior_rev <= 0 else rev / prior_rev - 1,
        "gross": _div(f.get("gross_profit"), rev),
        "operating": None if ebit is None or rev is None or rev <= 0 else ebit / rev,
        "ebitda": _div(f.get("ebitda"), rev),
        "net": None if ni is None or rev is None or rev <= 0 else ni / rev,
        "roa": None if ni is None or assets is None or assets <= 0 else ni / assets,
        "roe": None if ni is None or equity is None or equity <= 0 else ni / equity,
    }


def profitability_area(figs: list[Figures], currency: str) -> AreaReport:
    """Context only (the skill: profitability explains cash flow and gearing, it does not lead)."""
    years = [_year_profit(figs, i) for i in range(len(figs))]
    cur, prev = years[0], years[1] if len(years) > 1 else None
    net, pnet = cur["net"], prev["net"] if prev else None
    flags: list[str] = []
    if net is None:
        level = Level.NOT_ASSESSED
        why = "Revenue or net income was not available."
    else:
        if net < 0.02:
            level = Level.WEAK
        elif net < 0.05:
            level = Level.NEEDS_ATTENTION
        elif net < 0.10:
            level = Level.SATISFACTORY
        else:
            level = Level.STRONG if pnet is None or net >= pnet - 0.005 else Level.SATISFACTORY
        if net < 0:
            flags.append("Net loss for the period")
        if pnet is not None and pnet - net > 0.05:
            flags.append("Net margin fell by more than 5 percentage points")
            if level in (Level.STRONG, Level.SATISFACTORY):
                level = Level.NEEDS_ATTENTION
        why = f"Net margin {pct(net)}"
        if pnet is not None:
            why += f" (was {pct(pnet)})"
        why += f"; operating margin {pct(cur['operating'])}; EBITDA margin {pct(cur['ebitda'])}"
        if cur["growth"] is not None:
            why += f"; revenue changed {pct(cur['growth'])} on the year before"
        why += ". Shown for context: it does not change the draft amount."
    if net is None or pnet is None:
        trend = "No earlier year to compare"
    else:
        trend = (
            "Improving" if net > pnet + 0.005 else "Weakening" if net < pnet - 0.005 else "Stable"
        )
    specs = [
        ("Revenue", "money", "revenue"),
        ("Revenue growth on the year before", "pct", "growth"),
        ("Gross margin", "pct", "gross"),
        ("Operating margin", "pct", "operating"),
        ("EBITDA margin", "pct", "ebitda"),
        ("Net margin", "pct", "net"),
        ("Return on average assets", "pct", "roa"),
        ("Return on average equity", "pct", "roe"),
    ]
    metrics = [
        m
        for label, kind, key in specs
        if (m := _row(label, kind, [y[key] for y in years], currency))
    ]
    return AreaReport(
        key="profitability",
        title="Profitability (context)",
        status=STATUS_OF[level],
        finding=finding_word(level),
        trend=trend,
        why=why,
        flags=flags,
        metrics=metrics,
        feeds_draft=False,
    )


def efficiency_area(
    ratio_sets: list[dict[str, dict[str, Any]]], figs: list[Figures], currency: str
) -> AreaReport:
    """Shown for context. Without verified peer data an efficiency status would be a guess, so none is given."""
    turnover: list[float | None] = []
    inv_turnover: list[float | None] = []
    for i, f in enumerate(figs):
        prior = figs[i + 1] if i + 1 < len(figs) else None
        assets = _avg(f.get("total_assets"), prior.get("total_assets") if prior else None)
        turnover.append(_div(f.get("revenue"), assets))
        rev, gp = f.get("revenue"), f.get("gross_profit")
        cogs = None if rev is None or gp is None else rev - gp
        inv = _avg(f.get("inventory"), prior.get("inventory") if prior else None)
        inv_turnover.append(_div(cogs, inv))
    rows = [
        ("Asset turnover (revenue over average assets)", "times", turnover),
        ("Inventory turnover (cost of sales over average inventory)", "times", inv_turnover),
        (
            "Days of revenue in receivables",
            "days",
            [r["receivables"]["dso_days"] for r in ratio_sets],
        ),
    ]
    metrics = [m for label, kind, values in rows if (m := _row(label, kind, values, currency))]
    return AreaReport(
        key="efficiency",
        title="Efficiency and industry context (context)",
        status="NOT_ASSESSED",
        finding="Not assessed",
        trend="Not compared with peers",
        why=(
            "Peer, market-share and customer-concentration data are not connected, so efficiency is shown "
            "for context and is not given a status. Benchmarks are not used."
        ),
        flags=[],
        metrics=metrics,
        feeds_draft=False,
    )


def extra_flags(
    ratio_sets: list[dict[str, dict[str, Any]]], figs: list[Figures], currency: str
) -> list[FlagCheck]:
    """Red flags from the senior-analyst framework that the figures can answer (the rest cannot be assessed)."""
    cur = figs[0]
    years = [_year_profit(figs, i) for i in range(len(figs))]
    net, pnet = years[0]["net"], years[1]["net"] if len(years) > 1 else None
    rev, due = cur.get("revenue"), cur.get("debt_due_12m")
    share = _div(due, rev)
    fcf, ni = ratio_sets[0]["cash_flow"]["free_cash_flow"], cur.get("net_income")
    nd = ratio_sets[0]["gearing"]["net_debt_to_ebitda"]
    pnd = ratio_sets[1]["gearing"]["net_debt_to_ebitda"] if len(ratio_sets) > 1 else None
    margin = f"Net margin {pct(net)} against {pct(pnet)} the year before."
    due_text = f"Debt due within 12 months is {pct(share)} of revenue ({money(due, currency)})."
    fcf_text = f"Free cash flow {money(fcf, currency)} with net income {money(ni, currency)}."
    lev_text = f"Net debt to EBITDA {times(nd)} (was {times(pnd)}); net margin {pct(net)} (was {pct(pnet)})."
    rising = (
        None
        if nd is None or pnd is None or net is None or pnet is None
        else (nd > pnd and net < pnet)
    )
    return [
        _flag(
            "Net margin down by more than 5 percentage points on the year before",
            None if net is None or pnet is None else pnet - net > 0.05,
            margin,
            margin,
            "Net margin for two periods was not available.",
        ),
        _flag(
            "Debt due within 12 months above 20% of annual revenue",
            None if share is None else share > 0.20,
            due_text,
            due_text,
            "Debt due within 12 months or revenue was not available.",
        ),
        _flag(
            "Negative free cash flow despite profitable operations",
            None if fcf is None or ni is None else (fcf < 0 and ni > 0),
            fcf_text,
            fcf_text,
            "Free cash flow or net income was not available.",
        ),
        _flag(
            "Leverage rising while margins compress",
            rising,
            lev_text,
            lev_text,
            "Leverage or margins for two periods were not available.",
        ),
        FlagCheck(
            text="Largest customers above 50% of revenue",
            state="NOT_ASSESSABLE",
            detail="Customer concentration is not in the figures and no customer data is connected.",
        ),
        FlagCheck(
            text="Market share falling while the industry grows",
            state="NOT_ASSESSABLE",
            detail="Market share and industry growth data are not connected.",
        ),
    ]


def debt_service_block(
    ratio_sets: list[dict[str, dict[str, Any]]], figs: list[Figures], currency: str
) -> tuple[list[Metric], list[str]]:
    """Can cash from operations carry the debt falling due and the interest? Only what the figures show."""
    cover: list[float | None] = []
    ocf_cl: list[float | None] = []
    for r, f in zip(ratio_sets, figs, strict=True):
        ocf = r["cash_flow"]["operating_cash_flow"]
        service = (f.get("debt_due_12m") or 0.0) + (f.get("interest_expense") or 0.0)
        have = f.get("debt_due_12m") is not None or f.get("interest_expense") is not None
        cover.append(_div(ocf, service) if have else None)
        ocf_cl.append(_div(ocf, f.get("current_liabilities")))
    rows = [
        ("Cash from operations over debt due within 12 months plus interest", "times", cover),
        ("Cash from operations over current liabilities", "times", ocf_cl),
        (
            "Free cash flow after dividends and buybacks",
            "money",
            [r["cash_flow"]["fcf_after_distributions"] for r in ratio_sets],
        ),
        (
            "Cash less debt due within 12 months",
            "money",
            [r["liquidity"]["cash_less_debt_due_12m"] for r in ratio_sets],
        ),
    ]
    metrics = [m for label, kind, values in rows if (m := _row(label, kind, values, currency))]
    notes = []
    if cover[0] is not None:
        notes.append(
            f"Cash from operations covers debt due within 12 months plus interest {times(cover[0])}."
        )
    if ocf_cl[0] is not None:
        notes.append(
            f"Cash from operations is {times(ocf_cl[0])} of current liabilities "
            "(a common reference point is 0.40x)."
        )
    notes.append(
        "The debt maturity ladder, undrawn committed facilities, covenant headroom and refinancing options "
        "are not in the figures, so the ability to refinance could not be assessed."
    )
    return metrics, notes


def stress_block(
    ratio_sets: list[dict[str, dict[str, Any]]], figs: list[Figures], currency: str
) -> tuple[list[StressRow], str | None]:
    """Revenue falls and costs do not. A transparent illustration of how thin the cushion is, not a forecast."""
    f = figs[0]
    rev = f.get("revenue")
    ebit = f.get("operating_income") if f.get("operating_income") is not None else f.get("ebit")
    interest = f.get("interest_expense")
    ocf = ratio_sets[0]["cash_flow"]["operating_cash_flow"]
    if rev is None or rev <= 0 or ebit is None:
        return [], None

    def row(label: str, drop: float) -> StressRow:
        hit = rev * drop
        earnings = ebit - hit
        return StressRow(
            scenario=label,
            earnings=money(earnings, currency),
            interest_cover=times(
                None if interest is None or interest <= 0 else earnings / interest
            ),
            cash_from_operations=money(None if ocf is None else ocf - hit, currency),
        )

    rows = [row("As reported", 0.0), row("Revenue down 10%", 0.10), row("Revenue down 20%", 0.20)]
    note = (
        "Illustration only. It assumes costs do not fall when revenue falls (the worst case) and ignores tax, "
        "working capital and management action. It is not a forecast. Earnings here means operating profit (EBIT)."
    )
    return rows, note


def _concerns(areas: list[AreaReport], checks: list[FlagCheck], gaps: list[str]) -> list[str]:
    """Most important first: distressed areas, then flags to look at, then weak areas, then missing information."""
    out: list[str] = []
    out += [f"{a.title}: distressed. {a.why}" for a in areas if a.status == "DISTRESSED"]
    out += [f"{c.text}: {c.detail}" for c in checks if c.state == "TRIGGERED"]
    out += [f"{a.title}: weak. {a.why}" for a in areas if a.status == "WEAK"]
    out += [f"Not known: {g}" for g in gaps[:3]]
    return list(dict.fromkeys(out))


def _counts(core: list[AreaReport]) -> dict[str, int]:
    return {
        s: sum(a.status == s for a in core) for s in ("OK", "WEAK", "DISTRESSED", "NOT_ASSESSED")
    }


def _consolidated_why(core: list[AreaReport]) -> str:
    """The consolidated line in the status words (the analyzer's own word is shown beside each area)."""
    four = _counts([a for a in core if a.key in CORE])
    parts = [f"{four['OK']} OK", f"{four['WEAK']} weak", f"{four['DISTRESSED']} distressed"]
    if four["NOT_ASSESSED"]:
        parts.append(f"{four['NOT_ASSESSED']} not assessed")
    return (
        f"The four core areas (balance sheet, liquidity, gearing, cash flow): {', '.join(parts)}."
    )


def _executive_summary(
    core: list[AreaReport],
    profit: AreaReport,
    status: Status,
    why: str,
    strengths: list[str],
    weaknesses: list[str],
) -> str:
    counts = _counts(core)
    text = (
        f"Consolidated financial findings: {STATUS_WORD[status]}. {why} Of the five core areas, "
        f"{counts['OK']} are OK, {counts['WEAK']} weak and {counts['DISTRESSED']} distressed"
        + (
            f", and {counts['NOT_ASSESSED']} could not be assessed"
            if counts["NOT_ASSESSED"]
            else ""
        )
        + f". Profitability, shown for context, is {STATUS_WORD[profit.status]}."
    )
    good = [x.split(":")[0] for x in strengths if not x.startswith("Profitability")][:3]
    bad = [x.split(":")[0] for x in weaknesses if not x.startswith("Profitability")][:3]
    if good:
        text += " Strongest: " + ", ".join(good).lower() + "."
    if bad:
        text += " Needs most attention: " + ", ".join(bad).lower() + "."
    return text[:600]


def build_report(
    *,
    sections: dict[str, Section],
    order: tuple[str, ...],
    consolidated: tuple[Level, str],
    ratio_sets: list[dict[str, dict[str, Any]]],
    figure_sets: list[Figures],
    periods: list[str],
    currency: str,
    statements_label: str,
    audit_note: str,
    other_checks: list[OtherCheck],
    gaps: list[str],
    analyzer_version: str,
) -> AnalysisReport:
    ratios, figures = ratio_sets[0], figure_sets[0]
    prior_figures = figure_sets[1] if len(figure_sets) > 1 else None

    core = [
        AreaReport(
            key=key,
            title=sections[key].title,
            status=STATUS_OF[sections[key].level],
            finding=finding_word(sections[key].level),
            trend=sections[key].trend,
            why=sections[key].why,
            flags=sections[key].flags[:10],
            metrics=_metrics(key, ratio_sets, figure_sets, currency),
        )
        for key in order
    ]
    profit = profitability_area(figure_sets, currency)
    areas = [*core, profit, efficiency_area(ratio_sets, figure_sets, currency)]
    checks = [
        *red_flag_checklist(ratios, figures, prior_figures, currency),
        *extra_flags(ratio_sets, figure_sets, currency),
    ]
    strengths = [
        f"{s.title}: {finding_word(s.level).lower()}. {s.why}"
        for s in sections.values()
        if s.level in (Level.STRONG, Level.SATISFACTORY)
    ]
    weaknesses = []
    for s in sections.values():
        if s.level in (Level.NEEDS_ATTENTION, Level.WEAK):
            extra = f" Flags: {'; '.join(s.flags)}." if s.flags else ""
            weaknesses.append(f"{s.title}: {finding_word(s.level).lower()}. {s.why}{extra}")
        elif s.level is Level.NOT_ASSESSED:
            weaknesses.append(f"{s.title}: could not be assessed. {s.why}")
    if profit.status in ("WEAK", "DISTRESSED"):
        weaknesses.append(f"Profitability: {profit.finding.lower()}. {profit.why}")
    elif profit.status == "OK":
        strengths.append(f"Profitability: {profit.finding.lower()}. {profit.why}")
    level, _analyzer_why = consolidated
    why = _consolidated_why(core)
    unique_gaps = list(dict.fromkeys(gaps))
    ds_metrics, ds_notes = debt_service_block(ratio_sets, figure_sets, currency)
    stress, stress_note = stress_block(ratio_sets, figure_sets, currency)
    return AnalysisReport(
        basis=Basis(
            statements=statements_label,
            periods=periods,
            currency=currency,
            units=f"Figures shown in millions of {currency} unless stated",
            audit_note=audit_note,
            method=(
                "Financial-statement assessment method (five core areas), with profitability and "
                "efficiency added for context, as written rules"
            ),
        ),
        executive_summary=_executive_summary(
            core, profit, STATUS_OF[level], why, strengths, weaknesses
        ),
        areas=areas,
        consolidated_status=STATUS_OF[level],
        consolidated_finding=finding_word(level),
        consolidated_why=why,
        red_flags=checks,
        debt_service=ds_metrics,
        debt_service_notes=[n[:600] for n in ds_notes],
        stress=stress,
        stress_note=stress_note,
        key_concerns=[c[:600] for c in _concerns(areas, checks, unique_gaps)][:15],
        strengths=[s[:600] for s in strengths],
        weaknesses=[w[:600] for w in weaknesses],
        watch=[w[:600] for w in _watch(sections, ratios, checks)],
        gaps=[g[:600] for g in unique_gaps],
        other_checks=other_checks,
        analyzer_version=analyzer_version,
    )
