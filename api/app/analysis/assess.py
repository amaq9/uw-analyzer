"""Dimension assessments, red flags and the amount proposal (analyzer v2, recommendation policy v1.1).

This is the senior-analyst framework (liquidity, profitability, leverage, cash flow, efficiency and
sector) as written rules, so the same figures always give the same words. Each dimension is described
as Strong, Adequate, Concerning or Critical using the framework's own thresholds, with the reasons and
a trend against the year before. Internally these are the levels STRONG, SATISFACTORY, NEEDS_ATTENTION
and WEAK; the report shows the framework's words. A dimension is judged by its worst available metric,
because one critical metric (a current ratio under 1.0, say) is not offset by a good one.

The consolidated finding follows the recommendation policy: the four core dimensions (liquidity,
profitability, leverage, cash flow) must be critical together for the consolidated finding to be weak.
Efficiency and sector is shown but never assessed, because peer data is not connected.

The amount proposal is the analyst's judgement made explicit and bounded: it starts from the whole
amount requested and subtracts a fixed share for each core dimension that is concerning or critical
and for each piece of missing information. The server's policy then decides the outcome from that
proposal."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from app.analysis.dimensions import dimension_metrics
from app.analysis.ratios import Figures

ANALYZER_VERSION = "2"

NEEDS_ATTENTION_CUT = Decimal("0.05")
WEAK_CUT = Decimal("0.15")
MISSING_INFORMATION_CUT = Decimal("0.05")


class Level(StrEnum):
    STRONG = "STRONG"
    SATISFACTORY = "SATISFACTORY"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    WEAK = "WEAK"
    NOT_ASSESSED = "NOT_ASSESSED"


RANK = {Level.WEAK: 0, Level.NEEDS_ATTENTION: 1, Level.SATISFACTORY: 2, Level.STRONG: 3}
BAND_LEVEL = {3: Level.STRONG, 2: Level.SATISFACTORY, 1: Level.NEEDS_ATTENTION, 0: Level.WEAK}
SECTIONS = ("liquidity", "profitability", "leverage", "cash_flow", "efficiency")
TITLES = {
    "liquidity": "Liquidity",
    "profitability": "Profitability",
    "leverage": "Leverage",
    "cash_flow": "Cash flow",
    "efficiency": "Efficiency and sector",
}
CORE = ("liquidity", "profitability", "leverage", "cash_flow")


def money(millions: float | None, currency: str = "USD") -> str:
    if millions is None:
        return "not available"
    sign = "-" if millions < 0 else ""
    a = Decimal(str(abs(millions)))
    if a >= 1000:
        return f"{sign}{currency} {(a / 1000).quantize(Decimal('0.01'), ROUND_HALF_UP):,}bn"
    if a < 10:
        return f"{sign}{currency} {a.quantize(Decimal('0.01'), ROUND_HALF_UP)}m"
    return f"{sign}{currency} {a.quantize(Decimal('1'), ROUND_HALF_UP):,}m"


def times(x: float | None) -> str:
    return "not calculable" if x is None else f"{x:.2f}x"


def pct(x: float | None) -> str:
    return "not calculable" if x is None else f"{x * 100:.1f}%"


@dataclass
class Section:
    key: str
    level: Level
    why: str
    trend: str = "No earlier year to compare"
    flags: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return TITLES[self.key]


@dataclass
class YearContext:
    ratios: dict[str, dict[str, Any]]
    figures: Figures
    prior_figures: Figures | None = None


def _worst(bands: list[int | None]) -> Level:
    present = [b for b in bands if b is not None]
    return BAND_LEVEL[min(present)] if present else Level.NOT_ASSESSED


def _band_current(x: float | None) -> int | None:
    return None if x is None else 3 if x > 2.0 else 2 if x >= 1.5 else 1 if x >= 1.0 else 0


def _band_quick(x: float | None) -> int | None:
    return None if x is None else 3 if x > 1.2 else 2 if x >= 0.8 else 1 if x >= 0.6 else 0


def _band_ocf_cl(x: float | None) -> int | None:
    return None if x is None else 3 if x > 0.50 else 2 if x >= 0.30 else 1 if x >= 0.15 else 0


def _band_de(x: float | None) -> int | None:
    return None if x is None else 3 if x < 1.0 else 2 if x <= 1.5 else 1 if x <= 2.5 else 0


def _band_cover(x: float | None) -> int | None:
    return None if x is None else 3 if x > 4.0 else 2 if x >= 2.5 else 1 if x >= 2.0 else 0


def _band_fcf(x: float | None) -> int | None:
    return None if x is None else 3 if x > 0.20 else 2 if x >= 0.10 else 1 if x >= 0 else 0


def _band_conversion(ocf: float | None, ni: float | None, ratio: float | None) -> int | None:
    if ocf is None:
        return None
    if ocf <= 0:
        return 0
    if ni is None or ni <= 0 or ratio is None:
        return 3  # cash from operations is positive and at least covers a loss
    return 3 if ratio > 1.0 else 2 if ratio >= 1.0 else 1 if ratio >= 0.8 else 0


def _liquidity(c: YearContext, p: YearContext | None, cur: str) -> Section:
    m = dimension_metrics(c.ratios, c.figures, c.prior_figures)["liquidity"]
    cr, quick, ocf_cl = m["current_ratio"], m["quick_ratio"], m["ocf_to_current_liabilities"]
    ocf = c.ratios["cash_flow"]["operating_cash_flow"]
    if cr is None:
        return Section(
            "liquidity",
            Level.NOT_ASSESSED,
            "Current assets or current liabilities were not available.",
        )
    level = _worst([_band_current(cr), _band_quick(quick), _band_ocf_cl(ocf_cl)])
    flags = []
    if cr < 1.0:
        flags.append("Current ratio below 1.0")
    if quick is not None and quick < 0.6:
        flags.append("Quick ratio below 0.6")
    if ocf is not None and ocf < 0:
        flags.append("Negative cash from operations")
    buffer = m["cash_less_debt_due_12m"]
    if buffer is not None and buffer < 0:
        flags.append("Debt due within 12 months exceeds cash")
    prior_cr = (
        None
        if p is None
        else dimension_metrics(p.ratios, p.figures, p.prior_figures)["liquidity"]["current_ratio"]
    )
    if prior_cr is not None and cr < prior_cr:
        flags.append("Current ratio is lower than the year before")
    why = f"Current ratio {times(cr)}"
    if prior_cr is not None:
        why += f" (was {times(prior_cr)})"
    why += f" against a reference range of 1.5 to 2.0; quick ratio {times(quick)}"
    if ocf_cl is not None:
        why += f"; cash from operations is {times(ocf_cl)} of current liabilities (reference above 0.40)"
    if buffer is not None:
        why += f"; cash less debt due within 12 months is {money(buffer, cur)}"
    return Section("liquidity", level, why + ".", flags=flags)


def _profitability(c: YearContext, p: YearContext | None, cur: str) -> Section:
    m = dimension_metrics(c.ratios, c.figures, c.prior_figures)["profitability"]
    net, ebitda = m["net_margin"], m["ebitda_margin"]
    if net is None:
        return Section(
            "profitability", Level.NOT_ASSESSED, "Revenue or net income was not available."
        )
    prior_net = (
        None
        if p is None
        else dimension_metrics(p.ratios, p.figures, p.prior_figures)["profitability"]["net_margin"]
    )
    band = 3 if net > 0.10 else 2 if net >= 0.05 else 1 if net >= 0.02 else 0
    flags = []
    if net < 0:
        flags.append("Net loss for the period")
    if band == 3 and prior_net is not None and net < prior_net - 0.005:
        band = 2  # a strong margin that is not growing is adequate
    if prior_net is not None and prior_net - net > 0.05:
        flags.append("Net margin fell by more than 5 percentage points")
        band = min(band, 1)
    if ebitda is not None and ebitda < 0.12:
        flags.append("EBITDA margin below 12%")
        band = min(band, 1)
    why = f"Net margin {pct(net)}"
    if prior_net is not None:
        why += f" (was {pct(prior_net)})"
    why += f" against a reference of above 10%; operating margin {pct(m['operating_margin'])}"
    why += f"; EBITDA margin {pct(ebitda)} (reference 12 to 18%)"
    if m["growth"] is not None:
        why += f"; revenue changed {pct(m['growth'])} on the year before"
    return Section("profitability", BAND_LEVEL[band], why + ".", flags=flags)


def _leverage(c: YearContext, p: YearContext | None, cur: str) -> Section:
    m = dimension_metrics(c.ratios, c.figures, c.prior_figures)["leverage"]
    de, cover, nd = m["debt_to_equity"], m["interest_cover"], m["net_debt_to_ebitda"]
    debt, net_debt, equity = m["financial_debt"], m["net_debt"], m["equity"]
    if debt is None and net_debt is None:
        return Section("leverage", Level.NOT_ASSESSED, "Debt figures were not available.")
    flags = []
    bands = [_band_de(de), _band_cover(cover)]
    if equity is not None and equity <= 0:
        flags.append("Negative equity (a shareholders' deficit)")
        bands.append(0)
    ebitda = c.figures.get("ebitda")
    if nd is not None and nd > 3.0:
        flags.append("Net debt above 3 times EBITDA")
        bands.append(1)
    if net_debt is not None and net_debt > 0 and ebitda is not None and ebitda <= 0:
        flags.append("Net debt with no positive EBITDA to service it")
        bands.append(0)
    if de is not None and de > 2.5:
        flags.append("Debt to equity above 2.5")
    if cover is not None and cover < 2.0:
        flags.append("Interest cover below 2.0")
    level = _worst(bands)
    parts = []
    if de is not None:
        parts.append(
            f"debt to equity {times(de)} (reference below 1.0 is strong, above 2.5 is critical)"
        )
    elif equity is not None and equity <= 0:
        parts.append(f"equity is {money(equity, cur)}, so debt to equity is not meaningful")
    if cover is not None:
        parts.append(f"interest cover {times(cover)} (reference above 2.5)")
    if nd is not None:
        parts.append(f"net debt is {times(nd)} EBITDA (reference below 3.0)")
    elif net_debt is not None and net_debt <= 0:
        parts.append(f"net cash of {money(-net_debt, cur)}")
    if m["equity_ratio"] is not None:
        parts.append(f"equity is {pct(m['equity_ratio'])} of assets (reference above 40%)")
    parts.append(
        "debt service coverage needs the debt service schedule, which is not in the figures"
    )
    return Section("leverage", level, "; ".join(parts).capitalize() + ".", flags=flags)


def _cash_flow(c: YearContext, p: YearContext | None, cur: str) -> Section:
    m = dimension_metrics(c.ratios, c.figures, c.prior_figures)["cash_flow"]
    ocf, conv, fcf_margin = m["operating_cash_flow"], m["ocf_to_net_income"], m["fcf_margin"]
    after = m["fcf_after_distributions"]
    if ocf is None:
        return Section("cash_flow", Level.NOT_ASSESSED, "Operating cash flow was not available.")
    ni = c.figures.get("net_income")
    prior_ocf = (
        None
        if p is None
        else dimension_metrics(p.ratios, p.figures, p.prior_figures)["cash_flow"][
            "operating_cash_flow"
        ]
    )
    drop = None if prior_ocf is None or prior_ocf <= 0 else 1 - ocf / prior_ocf
    level = _worst([_band_conversion(ocf, ni, conv), _band_fcf(fcf_margin)])
    flags = []
    if ocf < 0:
        flags.append("Negative cash from operations")
    if conv is not None and conv < 1.0:
        flags.append("Cash from operations below net income")
    if after is not None and after < 0:
        flags.append("Free cash flow does not cover dividends and buybacks")
    if drop is not None and drop > 0.20:
        flags.append("Cash from operations fell by more than a fifth")
    if m["capex_to_depreciation"] is not None and m["capex_to_depreciation"] > 1.0:
        flags.append("Capital spending above depreciation")
    why = f"Cash from operations {money(ocf, cur)}"
    if drop is not None:
        why += f", {'down' if drop > 0 else 'up'} {abs(drop) * 100:.1f}% on the year before"
    if conv is not None:
        why += f", {times(conv)} net income (reference above 0.80)"
    if m["free_cash_flow"] is not None:
        why += f"; free cash flow {money(m['free_cash_flow'], cur)}"
    if fcf_margin is not None:
        why += f" or {pct(fcf_margin)} of revenue (reference above 10%)"
    if after is not None:
        why += f", {money(after, cur)} after dividends and buybacks"
    return Section("cash_flow", level, why + ".", flags=flags)


def _efficiency(c: YearContext, p: YearContext | None, cur: str) -> Section:
    return Section(
        "efficiency",
        Level.NOT_ASSESSED,
        "Peer, market-share and customer-concentration data are not connected, so efficiency and "
        "sector are shown for context and are not given a finding.",
    )


_RULES = {
    "liquidity": _liquidity,
    "profitability": _profitability,
    "leverage": _leverage,
    "cash_flow": _cash_flow,
    "efficiency": _efficiency,
}


def assess_year(c: YearContext, p: YearContext | None, currency: str = "USD") -> dict[str, Section]:
    return {key: rule(c, p, currency) for key, rule in _RULES.items()}


def assess(years: list[YearContext], currency: str = "USD") -> dict[str, Section]:
    """`years` is newest first. Trend compares each dimension with the same rules applied one year back."""
    linked = [
        YearContext(y.ratios, y.figures, years[i + 1].figures if i + 1 < len(years) else None)
        for i, y in enumerate(years)
    ]
    current = assess_year(linked[0], linked[1] if len(linked) > 1 else None, currency)
    if len(linked) > 1:
        before = assess_year(linked[1], linked[2] if len(linked) > 2 else None, currency)
        for key, section in current.items():
            earlier = before[key].level
            if section.level is Level.NOT_ASSESSED or earlier is Level.NOT_ASSESSED:
                continue
            delta = RANK[section.level] - RANK[earlier]
            section.trend = "Improving" if delta > 0 else "Weakening" if delta < 0 else "Stable"
    return current


def consolidated(sections: dict[str, Section]) -> tuple[Level, str]:
    """Policy: weak only when the core dimensions are critical together; strong only when all are strong."""
    core = [sections[key].level for key in CORE]
    assessed = [level for level in core if level is not Level.NOT_ASSESSED]
    if not assessed:
        return Level.NOT_ASSESSED, "The core dimensions could not be assessed."
    weak = sum(level is Level.WEAK for level in core)
    if weak >= 3:
        return Level.WEAK, f"{weak} of the 4 core dimensions are critical."
    if all(level is Level.STRONG for level in core):
        return Level.STRONG, "All four core dimensions are strong."
    return Level.SATISFACTORY, "The core dimensions are not critical together."


@dataclass
class Factor:
    code: str
    explanation: str
    cut: Decimal


def propose_fraction(
    sections: dict[str, Section], *, adverse_search_complete: bool, sector_outlook_assessed: bool
) -> tuple[Decimal, list[Factor]]:
    """The share of the amount requested the analyst proposes, and why (never above 1)."""
    factors: list[Factor] = []
    core = [sections[key] for key in CORE]
    attention = [s for s in core if s.level is Level.NEEDS_ATTENTION]
    weak = [s for s in core if s.level is Level.WEAK]
    missing_sections = [s for s in core if s.level is Level.NOT_ASSESSED]
    if attention or weak:
        cut = NEEDS_ATTENTION_CUT * len(attention) + WEAK_CUT * len(weak)
        names = ", ".join(s.title.lower() for s in attention + weak)
        factors.append(
            Factor(
                "acceptable_not_strong",
                f"Not strong enough to support the whole amount: {names}.",
                cut,
            )
        )
    gaps = [f"{s.title.lower()} could not be assessed" for s in missing_sections]
    if not adverse_search_complete:
        gaps.append("the adverse-information search is incomplete")
    if not sector_outlook_assessed:
        gaps.append("the sector outlook was not assessed")
    if gaps:
        factors.append(
            Factor(
                "missing_information",
                "Information is missing: " + "; ".join(gaps) + ".",
                MISSING_INFORMATION_CUT * len(gaps),
            )
        )
    fraction = max(Decimal(0), Decimal(1) - sum((f.cut for f in factors), Decimal(0)))
    return fraction, factors
