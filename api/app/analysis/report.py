"""Build the written-up analysis (Step 1) from the analyzer's figures and findings.

Pure and deterministic: the same figures give the same report. Nothing here decides anything. It lays
out the five dimensions of the analyst framework (liquidity, profitability, leverage, cash flow,
efficiency and sector) with their figures and reference ranges, runs the red-flag checklist as prompts
for attention, and closes with strengths, weaknesses, what to watch and what is not known."""

from typing import Any, Literal

from app.analysis.assess import CORE, Level, Section, money, pct, times
from app.analysis.dimensions import dimension_metrics
from app.analysis.dimensions import div as _div
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


FINDING_WORD = {
    Level.STRONG: "Strong",
    Level.SATISFACTORY: "Adequate",
    Level.NEEDS_ATTENTION: "Concerning",
    Level.WEAK: "Critical",
    Level.NOT_ASSESSED: "Not assessed",
}


def finding_word(level: Level) -> str:
    return FINDING_WORD[level]


# (label, metric key, how to show it, the framework's reference range). Reference ranges are the
# framework's own and are indicative only: no verified peer data is used.
_SPECS: dict[str, list[tuple[str, str, str, str]]] = {
    "liquidity": [
        ("Current ratio", "current_ratio", "times", "1.5 to 2.0"),
        ("Quick ratio", "quick_ratio", "times", "1.0 to 1.5"),
        ("Cash ratio", "cash_ratio", "times", "0.5 to 1.0"),
        ("Working capital", "working_capital", "money", ""),
        (
            "Cash from operations over current liabilities",
            "ocf_to_current_liabilities",
            "times",
            "above 0.40",
        ),
        ("Cash less debt due within 12 months", "cash_less_debt_due_12m", "money", ""),
    ],
    "profitability": [
        ("Revenue", "revenue", "money", ""),
        ("Revenue growth on the year before", "growth", "pct", ""),
        ("Gross margin", "gross_margin", "pct", ""),
        ("Operating margin", "operating_margin", "pct", ""),
        ("EBITDA margin", "ebitda_margin", "pct", "12 to 18%"),
        ("Net margin", "net_margin", "pct", "above 10% strong, 5 to 10% adequate"),
        ("Return on average assets", "return_on_assets", "pct", ""),
        ("Return on average equity", "return_on_equity", "pct", ""),
    ],
    "leverage": [
        ("Financial debt", "financial_debt", "money", ""),
        ("Net debt (negative is net cash)", "net_debt", "money", ""),
        ("Debt to equity", "debt_to_equity", "times", "below 1.0 strong, above 2.5 critical"),
        ("Debt to assets", "debt_to_assets", "times", "below 0.60"),
        ("Equity as a share of assets", "equity_ratio", "pct", "above 40%"),
        ("Interest cover (EBIT over interest)", "interest_cover", "times", "above 2.5"),
        ("Net debt to EBITDA", "net_debt_to_ebitda", "times", "below 3.0"),
    ],
    "cash_flow": [
        ("Cash from operations", "operating_cash_flow", "money", ""),
        ("Free cash flow (after capital spending)", "free_cash_flow", "money", ""),
        ("Free cash flow as a share of revenue", "fcf_margin", "pct", "above 10%"),
        (
            "Cash from operations as a multiple of net income",
            "ocf_to_net_income",
            "times",
            "above 0.80",
        ),
        ("Capital spending over depreciation", "capex_to_depreciation", "times", "below 1.0"),
        ("Dividends and buybacks", "distributions", "money", ""),
        ("Free cash flow after dividends and buybacks", "fcf_after_distributions", "money", ""),
        ("Net change in cash", "net_change_in_cash", "money", ""),
    ],
    "efficiency": [
        ("Asset turnover (revenue over average assets)", "asset_turnover", "times", ""),
        ("Days of revenue in receivables", "dso_days", "days", ""),
        (
            "Inventory turnover (cost of sales over average inventory)",
            "inventory_turnover",
            "times",
            "",
        ),
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


def _row(
    label: str, kind: str, values: list[float | None], currency: str, reference: str = ""
) -> Metric | None:
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
        reference=reference,
    )


def _metrics(
    key: str, metric_sets: list[dict[str, dict[str, float | None]]], currency: str
) -> list[Metric]:
    out: list[Metric] = []
    for label, name, kind, reference in _SPECS[key]:
        row = _row(label, kind, [m[key].get(name) for m in metric_sets], currency, reference)
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


def _metric_sets(
    ratio_sets: list[dict[str, dict[str, Any]]], figs: list[Figures]
) -> list[dict[str, dict[str, float | None]]]:
    return [
        dimension_metrics(r, f, figs[i + 1] if i + 1 < len(figs) else None)
        for i, (r, f) in enumerate(zip(ratio_sets, figs, strict=True))
    ]


def extra_flags(
    ratio_sets: list[dict[str, dict[str, Any]]], figs: list[Figures], currency: str
) -> list[FlagCheck]:
    """Red flags from the analyst framework that the figures can answer (the rest cannot be assessed)."""
    cur = figs[0]
    ms = _metric_sets(ratio_sets, figs)
    net = ms[0]["profitability"]["net_margin"]
    pnet = ms[1]["profitability"]["net_margin"] if len(ms) > 1 else None
    rev, due = cur.get("revenue"), cur.get("debt_due_12m")
    share = _div(due, rev)
    fcf, ni = ratio_sets[0]["cash_flow"]["free_cash_flow"], cur.get("net_income")
    nd = ratio_sets[0]["gearing"]["net_debt_to_ebitda"]
    pnd = ratio_sets[1]["gearing"]["net_debt_to_ebitda"] if len(ratio_sets) > 1 else None
    de = ms[0]["leverage"]["debt_to_equity"]
    conv = ms[0]["cash_flow"]["ocf_to_net_income"]
    margin = f"Net margin {pct(net)} against {pct(pnet)} the year before."
    due_text = f"Debt due within 12 months is {pct(share)} of revenue ({money(due, currency)})."
    fcf_text = f"Free cash flow {money(fcf, currency)} with net income {money(ni, currency)}."
    lev_text = f"Net debt to EBITDA {times(nd)} (was {times(pnd)}); net margin {pct(net)} (was {pct(pnet)})."
    de_text = f"Debt to equity is {times(de)}."
    conv_text = f"Cash from operations is {times(conv)} net income."
    rising = (
        None
        if nd is None or pnd is None or net is None or pnet is None
        else (nd > pnd and net < pnet)
    )
    return [
        _flag(
            "Debt to equity above 2.5",
            None if de is None else de > 2.5,
            de_text,
            de_text,
            "Debt to equity was not available (no debt, or no positive equity).",
        ),
        _flag(
            "Cash from operations below 80% of net income",
            None if conv is None else conv < 0.8,
            conv_text,
            conv_text,
            "Cash from operations or positive net income was not available.",
        ),
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
        FlagCheck(
            text="Covenant violations or near-misses",
            state="NOT_ASSESSABLE",
            detail="Covenants are in the loan documents, which are not part of the figures.",
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
    """The consolidated line in the status words (the framework's own word is shown beside each area)."""
    c = _counts(core)
    parts = [f"{c['OK']} OK", f"{c['WEAK']} weak", f"{c['DISTRESSED']} distressed"]
    if c["NOT_ASSESSED"]:
        parts.append(f"{c['NOT_ASSESSED']} not assessed")
    return f"The four core dimensions (liquidity, profitability, leverage, cash flow): {', '.join(parts)}."


def _executive_summary(
    core: list[AreaReport],
    status: Status,
    why: str,
    strengths: list[str],
    weaknesses: list[str],
) -> str:
    text = (
        f"Consolidated financial findings: {STATUS_WORD[status]}. {why} "
        "Efficiency and sector are shown for context and are not assessed, because peer data is not connected."
    )
    good = [x.split(":")[0] for x in strengths][:3]
    bad = [x.split(":")[0] for x in weaknesses][:3]
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

    metric_sets = _metric_sets(ratio_sets, figure_sets)
    areas = [
        AreaReport(
            key=key,
            title=sections[key].title,
            status=STATUS_OF[sections[key].level],
            finding=finding_word(sections[key].level),
            trend=sections[key].trend,
            why=sections[key].why,
            flags=sections[key].flags[:10],
            metrics=_metrics(key, metric_sets, currency),
            feeds_draft=key in CORE,
        )
        for key in order
    ]
    core = [a for a in areas if a.key in CORE]
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
        elif s.level is Level.NOT_ASSESSED and s.key in CORE:
            weaknesses.append(f"{s.title}: could not be assessed. {s.why}")
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
                "Analyst framework: liquidity, profitability, leverage, cash flow, efficiency and sector, "
                "as written rules with the framework's reference ranges"
            ),
        ),
        executive_summary=_executive_summary(core, STATUS_OF[level], why, strengths, weaknesses),
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
