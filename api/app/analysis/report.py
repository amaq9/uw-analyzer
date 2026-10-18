"""Build the written-up analysis (Step 1) from the analyzer's figures and findings.

Pure and deterministic: the same figures give the same report. Nothing here decides anything. It lays
out the five dimensions of the analyst framework (liquidity, profitability, leverage, cash flow,
efficiency and sector) with their figures and reference ranges, runs the red-flag checklist as prompts
for attention, and closes with strengths, weaknesses, what to watch and what is not known."""

from datetime import date, timedelta
from typing import Any, Literal

from app.analysis.assess import CORE, Level, Section, money, pct, times
from app.analysis.dimensions import dimension_metrics
from app.analysis.dimensions import div as _div
from app.analysis.ratios import Figures
from app.ratings.scale import AGENCY_NAMES
from app.ratings.schemas import PublishedRatingOut
from app.recommendation.analysis_report import (
    AnalysisReport,
    AreaReport,
    Basis,
    FlagCheck,
    Metric,
    NoteFinding,
    NotesReview,
    OtherCheck,
    Status,
    StressRow,
)

GOING_CONCERN_CHECK = "Going-concern language, covenant breach, auditor change or qualification"
CUSTOMER_CHECK = "Largest customers above 50% of revenue"
COVENANT_CHECK = "Covenant violations or near-misses"

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


def _tax_rate(f: Figures) -> float | None:
    """The effective tax rate the company actually paid on its profit, or None when it cannot be worked out."""
    pretax, net = f.get("pretax_income"), f.get("net_income")
    if pretax is None or net is None or pretax <= 0:
        return None
    rate = (pretax - net) / pretax
    return min(max(rate, 0.0), 0.40)


STANDARD_DEFINITIONS = [
    "EBIT is operating profit before interest and tax. EBITDA is EBIT plus depreciation and amortisation.",
    "Net debt is financial debt plus lease liabilities, less cash and short-term investments. A negative figure is net cash.",
    "Debt to equity is financial debt plus lease liabilities, divided by shareholders' equity.",
    "Interest cover is EBIT divided by interest expense. The quick ratio is current assets less inventory, divided by current liabilities.",
    "Free cash flow is cash from operations less capital expenditure. Net margin is net income divided by revenue.",
]


def stress_block(
    ratio_sets: list[dict[str, dict[str, Any]]], figs: list[Figures], currency: str
) -> tuple[list[StressRow], str | None]:
    """What happens to operating profit, interest cover and operating cash flow if revenue falls.

    Main case: the cost of sales falls with sales, so only the gross profit on the lost revenue is lost and
    operating expenses stay (a standard analyst downside). Extreme case: no cost falls at all, so the whole of
    the lost revenue is lost profit. Tax is allowed to fall with profit only while the stressed profit stays
    positive. Working capital release and management action are ignored. Arithmetic, not a forecast."""
    f = figs[0]
    rev = f.get("revenue")
    ebit = f.get("operating_income") if f.get("operating_income") is not None else f.get("ebit")
    interest = f.get("interest_expense")
    ocf = ratio_sets[0]["cash_flow"]["operating_cash_flow"]
    gross = f.get("gross_profit")
    if rev is None or rev <= 0 or ebit is None:
        return [], None
    margin = None if gross is None else gross / rev
    rate = _tax_rate(f)
    pretax = f.get("pretax_income")

    def row(label: str, drop: float, flow_through: float) -> StressRow:
        """`flow_through` is the share of the lost revenue that is lost as profit (0 to 1)."""
        loss = rev * drop * flow_through
        earnings = ebit - loss
        cash: float | None = None
        if ocf is not None:
            relief = 0.0
            if rate is not None and pretax is not None:
                relief = rate * (
                    pretax - max(pretax - loss, 0.0)
                )  # tax falls only while profit stays positive
            cash = ocf - loss + relief
        return StressRow(
            scenario=label,
            earnings=money(earnings, currency),
            interest_cover=times(
                None if interest is None or interest <= 0 else earnings / interest
            ),
            cash_from_operations=money(cash, currency),
        )

    if margin is not None and 0 < margin <= 1:
        rows = [
            row("As reported", 0.0, 1.0),
            row("Revenue down 10%, cost of sales falls with sales", 0.10, margin),
            row("Revenue down 20%, cost of sales falls with sales", 0.20, margin),
            row("Revenue down 10%, no cost saving at all (extreme)", 0.10, 1.0),
        ]
        break_even = ebit / (rev * margin) if ebit > 0 else 0.0
        extra = (
            f" Gross margin is {pct(margin)}; operating profit reaches zero if revenue falls about {break_even * 100:.1f}%."
            if ebit > 0
            else " Operating profit is already at or below zero."
        )
        basis = (
            "Main rows: the cost of sales falls with sales and operating expenses stay the same."
            + extra
            + " The last row is the extreme: no cost falls at all, so the whole of the lost revenue is lost profit."
        )
    else:
        rows = [
            row("As reported", 0.0, 1.0),
            row("Revenue down 10%, no cost saving at all (extreme)", 0.10, 1.0),
            row("Revenue down 20%, no cost saving at all (extreme)", 0.20, 1.0),
        ]
        basis = (
            "Gross profit is not available, so only the extreme case is shown: no cost falls when revenue falls, so "
            "the whole of the lost revenue is lost profit."
        )
    tax = (
        f" Tax is assumed to fall with profit at the {pct(rate)} the company paid, only while profit stays positive."
        if rate is not None
        else " Tax relief is not assumed."
    )
    note = (
        "Illustration only, not a forecast. "
        + basis
        + tax
        + " Working capital release and management action are ignored. Earnings here means operating profit (EBIT)."
    )
    return rows, note


def _first_quote(finding: NoteFinding) -> str:
    return f" “{finding.quotes[0].text[:220]}”" if finding.quotes else ""


def notes_flags(
    review: NotesReview | None, largest_customer: float | None = None
) -> dict[str, FlagCheck]:
    """The three checklist items that only the printed filing can answer, from what it says.
    Without the filing they stay not assessable. A topic the filing does not discuss is never read as clear."""
    if review is None:
        return {}
    by = {f.topic: f for f in review.findings}

    def get(topic: str) -> NoteFinding | None:
        return by.get(topic)

    out: dict[str, FlagCheck] = {}
    gc, op, ch, cov = (
        get("GOING_CONCERN"),
        get("AUDITOR_OPINION"),
        get("AUDITOR_CHANGE"),
        get("COVENANTS"),
    )
    hits = [f for f in (gc, op, ch, cov) if f is not None and f.state == "CONCERN"]
    if hits:
        out[GOING_CONCERN_CHECK] = FlagCheck(
            text=GOING_CONCERN_CHECK,
            state="TRIGGERED",
            detail=(
                "In the filing: "
                + " ".join(f"{f.title}: {f.summary}" for f in hits)
                + _first_quote(hits[0])
            )[:600],
        )
    elif gc is not None and op is not None and op.state != "NOT_FOUND":
        parts = [
            f"{f.title}: {f.summary}"
            for f in (gc, op, ch)
            if f is not None and f.state != "NOT_FOUND"
        ]
        out[GOING_CONCERN_CHECK] = FlagCheck(
            text=GOING_CONCERN_CHECK,
            state="CLEAR",
            detail=("Read in the filing. " + " ".join(parts))[:600],
        )
    else:
        out[GOING_CONCERN_CHECK] = FlagCheck(
            text=GOING_CONCERN_CHECK,
            state="NOT_ASSESSABLE",
            detail="The filing was read but the auditor's report was not found in its text, so this could not be settled.",
        )

    cust = get("CUSTOMER_CONCENTRATION")
    if cust is not None and cust.state == "CONCERN":
        out[CUSTOMER_CHECK] = FlagCheck(
            text=CUSTOMER_CHECK, state="TRIGGERED", detail=(cust.summary + _first_quote(cust))[:600]
        )
    elif cust is not None and cust.state in ("NO_CONCERN", "INFO"):
        out[CUSTOMER_CHECK] = FlagCheck(
            text=CUSTOMER_CHECK, state="CLEAR", detail=(cust.summary + _first_quote(cust))[:600]
        )
    else:
        out[CUSTOMER_CHECK] = FlagCheck(
            text=CUSTOMER_CHECK,
            state="NOT_ASSESSABLE",
            detail="The filing does not state a customer concentration, so it could not be checked.",
        )

    if cov is not None and cov.state == "CONCERN":
        out[COVENANT_CHECK] = FlagCheck(
            text=COVENANT_CHECK, state="TRIGGERED", detail=(cov.summary + _first_quote(cov))[:600]
        )
    elif cov is not None and cov.state == "NO_CONCERN":
        out[COVENANT_CHECK] = FlagCheck(
            text=COVENANT_CHECK,
            state="CLEAR",
            detail=(cov.summary + " The size of the headroom is not stated." + _first_quote(cov))[
                :600
            ],
        )
    else:
        out[COVENANT_CHECK] = FlagCheck(
            text=COVENANT_CHECK,
            state="NOT_ASSESSABLE",
            detail="The filing gives no statement that the covenants were met or breached, so this could not be checked.",
        )
    return out


def rating_flags(ratings: list[PublishedRatingOut], as_of: date) -> list[FlagCheck]:
    """The framework's ratings red flags. They need a recorded rating; without one they are not assessable."""
    if not ratings:
        detail = "No published rating is recorded for this company, so this could not be checked."
        return [
            FlagCheck(text=text, state="NOT_ASSESSABLE", detail=detail)
            for text in (
                "Recent downgrade by an agency (within 6 months)",
                "Negative outlook from an agency",
                "Speculative grade from an agency",
                "Rating under review by an agency",
            )
        ]

    def names(selected: list[PublishedRatingOut]) -> str:
        return ", ".join(f"{AGENCY_NAMES[r.agency]} {r.grade}" for r in selected)

    cutoff = as_of - timedelta(days=183)
    recent = [
        r
        for r in ratings
        if r.change == "DOWNGRADE" and r.last_action_on and r.last_action_on >= cutoff
    ]
    negative = [r for r in ratings if r.outlook == "NEGATIVE"]
    speculative = [r for r in ratings if not r.investment_grade]
    review = [r for r in ratings if r.under_review]
    recorded = names(ratings)

    def flag(text: str, hits: list[PublishedRatingOut], yes: str, no: str) -> FlagCheck:
        return FlagCheck(
            text=text,
            state="TRIGGERED" if hits else "CLEAR",
            detail=f"{yes}: {names(hits)}." if hits else f"{no} ({recorded}).",
        )

    return [
        flag(
            "Recent downgrade by an agency (within 6 months)",
            recent,
            "Downgraded within the last six months",
            "No recorded downgrade in the last six months",
        ),
        flag(
            "Negative outlook from an agency",
            negative,
            "Negative outlook",
            "No negative outlook recorded",
        ),
        flag(
            "Speculative grade from an agency",
            speculative,
            "Below investment grade",
            "Investment grade",
        ),
        flag(
            "Rating under review by an agency",
            review,
            "Under review",
            "Not recorded as under review",
        ),
    ]


def reconcile(core: list[AreaReport], ratings: list[PublishedRatingOut]) -> str:
    """Do the published ratings and the financial analysis point the same way? Words only; the draft is
    not changed by the answer."""
    if not ratings:
        return (
            "No published rating is recorded, so there is nothing to compare with the financial analysis. "
            "That is not a finding about the company: most private companies have none."
        )
    counts = _counts(core)
    sound = counts["DISTRESSED"] == 0 and counts["WEAK"] <= 1
    stressed = counts["DISTRESSED"] >= 2
    investment = [r for r in ratings if r.investment_grade]
    speculative = [r for r in ratings if not r.investment_grade]
    listed = ", ".join(f"{AGENCY_NAMES[r.agency]} {r.grade}" for r in ratings)
    if investment and not speculative and sound:
        text = (
            f"Published ratings ({listed}) are investment grade and the financial analysis shows no "
            "critical dimension: the two point the same way."
        )
    elif speculative and stressed:
        text = (
            f"Published ratings ({listed}) are below investment grade and the financial analysis shows "
            "strain in several dimensions: the two point the same way."
        )
    elif investment and stressed:
        text = (
            f"The two differ. Published ratings ({listed}) include investment grade, yet the financial "
            "analysis shows strain in several dimensions. Possible reasons are a lag in the agency's view, "
            "support or recovery expected by the agency, or factors that are not in the figures. Look closer; "
            "neither overrides the other."
        )
    elif speculative and sound:
        text = (
            f"The two differ. Published ratings ({listed}) include a grade below investment grade, yet the "
            "financial analysis shows no critical dimension. The grade may reflect factors not in the figures "
            "such as size, sector or the agency's leverage targets. Look closer; neither overrides the other."
        )
    else:
        text = (
            f"Published ratings ({listed}) are shown beside a financial picture that is mixed, so no "
            "alignment can be stated."
        )
    if any(r.outlook == "NEGATIVE" or r.under_review for r in ratings):
        text += " An agency shows a negative outlook or has a rating under review."
    secondary = [r for r in ratings if r.source_kind != "AGENCY_SITE"]
    if secondary:
        labels = [f"{AGENCY_NAMES[r.agency]} {r.grade}" for r in secondary]
        names = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]
        if len(labels) == 1:
            text += (
                f" {names} came from a secondary source, not the agency's own website. "
                "Confirm it on the agency's site, which is the main source."
            )
        else:
            text += (
                f" {names} came from secondary sources, not the agencies' own websites. "
                "Confirm them on the agencies' sites, which are the main sources."
            )
    return text


def _concerns(
    areas: list[AreaReport],
    checks: list[FlagCheck],
    gaps: list[str],
    notes: NotesReview | None = None,
) -> list[str]:
    """Most important first: distressed areas, then flags to look at, then weak areas, then missing information."""
    out: list[str] = []
    out += [f"{a.title}: {a.finding.lower()}. {a.why}" for a in areas if a.status == "DISTRESSED"]
    out += [f"{c.text}: {c.detail}" for c in checks if c.state == "TRIGGERED"]
    out += [f"{a.title}: {a.finding.lower()}. {a.why}" for a in areas if a.status == "WEAK"]
    out += [
        f"In the filing: {f.title}: {f.summary}"
        for f in (notes.findings if notes else [])
        if f.state == "CONCERN"
    ]
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


def _headline_status(level: Level, core: list[AreaReport]) -> Status:
    """The consolidated colour. The policy treats the findings as weak only when the core dimensions are
    critical together (that test is unchanged), but the headline must not read OK above dimensions that
    are not: OK only when no core dimension is Concerning or Critical."""
    counts = _counts(core)
    if level is Level.NOT_ASSESSED or counts["NOT_ASSESSED"] == len(core):
        return "NOT_ASSESSED"
    if level is Level.WEAK:
        return "DISTRESSED"
    if counts["WEAK"] or counts["DISTRESSED"]:
        return "WEAK"
    return "OK"


def _headline_word(level: Level, status: Status) -> str:
    return {
        "DISTRESSED": "Critical",
        "WEAK": "Concerning",
        "NOT_ASSESSED": "Not assessed",
    }.get(status, finding_word(level))


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
    ratings: list[PublishedRatingOut] | None = None,
    as_of: date | None = None,
    definitions: list[str] | None = None,
    notes: NotesReview | None = None,
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
        *rating_flags(ratings or [], as_of or date.today()),
    ]
    from_notes = notes_flags(notes)
    checks = [from_notes.get(c.text, c) for c in checks]
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
    headline = _headline_status(level, core)
    unique_gaps = list(dict.fromkeys(gaps))
    all_definitions = list(dict.fromkeys(STANDARD_DEFINITIONS + (definitions or [])))
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
        executive_summary=_executive_summary(core, headline, why, strengths, weaknesses),
        areas=areas,
        consolidated_status=headline,
        consolidated_finding=_headline_word(level, headline),
        consolidated_why=why,
        red_flags=checks,
        debt_service=ds_metrics,
        debt_service_notes=[n[:600] for n in ds_notes],
        stress=stress,
        stress_note=stress_note,
        key_concerns=[c[:600] for c in _concerns(areas, checks, unique_gaps, notes)][:15],
        published_ratings=ratings or [],
        ratings_reconciliation=reconcile(core, ratings or [])[:600],
        strengths=[s[:600] for s in strengths],
        weaknesses=[w[:600] for w in weaknesses],
        watch=[w[:600] for w in _watch(sections, ratios, checks)],
        gaps=[g[:600] for g in unique_gaps],
        definitions=[d[:600] for d in all_definitions][:20],
        notes_review=notes,
        other_checks=other_checks,
        analyzer_version=analyzer_version,
    )
