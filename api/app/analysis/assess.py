"""Section assessments, red flags and the amount proposal (analyzer v1).

This is the financial-statement-assessment method as written rules, so the same figures always give
the same words. Each of the five sections is described as Strong, Satisfactory, Needs attention or
Weak (never a number, rating or colour: ADR 0004), with the reasons and a trend against the year
before. The consolidated finding follows the Product Owner's recommendation policy v1.0: the core
sections (balance sheet, liquidity, gearing, cash flow) must be weak together for the consolidated
finding to be weak.

The amount proposal is the analyst's judgement made explicit and bounded: it starts from the whole
amount requested and subtracts a fixed share for each section that needs attention or is weak and for
each piece of missing information. The server's policy then decides the outcome from that proposal."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Any

from app.analysis.ratios import Figures

ANALYZER_VERSION = "1"

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
SECTIONS = ("balance_sheet", "liquidity", "gearing", "receivables", "cash_flow")
TITLES = {
    "balance_sheet": "Balance sheet strength",
    "liquidity": "Liquidity",
    "gearing": "Gearing",
    "receivables": "Accounts receivable",
    "cash_flow": "Cash flow generation",
}
CORE = ("balance_sheet", "liquidity", "gearing", "cash_flow")


def money(millions: float | None, currency: str = "USD") -> str:
    if millions is None:
        return "not available"
    sign = "-" if millions < 0 else ""
    a = Decimal(str(abs(millions)))
    if a >= 1000:
        return f"{sign}{currency} {(a / 1000).quantize(Decimal('0.01'), ROUND_HALF_UP):,}bn"
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


def _growth(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev <= 0:
        return None
    return cur / prev - 1


def _balance(c: YearContext, p: YearContext | None, cur: str) -> Section:
    r = c.ratios["balance_sheet"]
    eq, to_assets = r["equity"], r["equity_to_assets"]
    if eq is None or to_assets is None:
        return Section(
            "balance_sheet", Level.NOT_ASSESSED, "Equity or total assets were not available."
        )
    intang_a, intang_e = (
        r["goodwill_and_intangibles_to_assets"],
        r["goodwill_and_intangibles_to_equity"],
    )
    flags = []
    if eq <= 0:
        flags.append("Negative equity (a shareholders' deficit)")
    if intang_e is not None and intang_e > 1.0:
        flags.append("Goodwill and intangibles exceed equity")
    if eq <= 0 or to_assets < 0.10 or (intang_e is not None and intang_e > 1.0):
        level = Level.WEAK
    elif to_assets >= 0.30 and (intang_a is None or intang_a < 0.20):
        level = Level.STRONG
    else:
        level = Level.SATISFACTORY
    why = f"Equity is {money(eq, cur)}, {pct(to_assets)} of total assets"
    why += (
        f"; goodwill and intangibles are {pct(intang_a)} of assets."
        if intang_a is not None
        else "."
    )
    return Section("balance_sheet", level, why, flags=flags)


def _liquidity(c: YearContext, p: YearContext | None, cur: str) -> Section:
    r = c.ratios["liquidity"]
    cr, quick, buffer = r["current_ratio"], r["quick_ratio"], r["cash_less_debt_due_12m"]
    if cr is None:
        return Section(
            "liquidity",
            Level.NOT_ASSESSED,
            "Current assets or current liabilities were not available.",
        )
    flags = []
    if cr < 1.0:
        flags.append("Current ratio below 1.0")
    if quick is not None and quick < 0.6:
        flags.append("Quick ratio below 0.6")
    if buffer is not None and buffer < 0:
        flags.append("Debt due within 12 months exceeds cash")
    if cr < 1.0:
        level = Level.WEAK
    elif cr < 1.2 or flags:
        level = Level.NEEDS_ATTENTION
    elif cr >= 2.0 and (quick is None or quick >= 1.0):
        level = Level.STRONG
    else:
        level = Level.SATISFACTORY
    why = f"Current ratio {times(cr)}"
    if p and p.ratios["liquidity"]["current_ratio"] is not None:
        why += f" (was {times(p.ratios['liquidity']['current_ratio'])})"
    why += f", quick ratio {times(quick)}"
    if buffer is not None:
        why += f"; cash less debt due within 12 months is {money(buffer, cur)}"
    return Section("liquidity", level, why + ".", flags=flags)


def _gearing(c: YearContext, p: YearContext | None, cur: str) -> Section:
    r = c.ratios["gearing"]
    nd_ebitda, cover, de = r["net_debt_to_ebitda"], r["interest_cover"], r["debt_to_equity"]
    before_leases = r["net_debt_before_leases"]
    if r["financial_debt"] is None and before_leases is None:
        return Section("gearing", Level.NOT_ASSESSED, "Debt figures were not available.")
    flags = []
    if nd_ebitda is not None and nd_ebitda > 3.0:
        flags.append("Net debt above 3 times EBITDA")
    if cover is not None and cover < 2.0:
        flags.append("Interest cover below 2.0x")
    weak = (nd_ebitda is not None and nd_ebitda > 4.0) or (cover is not None and cover < 1.5)
    attention = bool(flags) or (de is not None and de > 3.0)
    net_cash = before_leases is not None and before_leases <= 0
    if weak:
        level = Level.WEAK
    elif attention:
        level = Level.NEEDS_ATTENTION
    elif (net_cash and (cover is None or cover >= 4.0)) or (
        nd_ebitda is not None and nd_ebitda < 1.0 and (cover is None or cover >= 6.0)
    ):
        level = Level.STRONG
    else:
        level = Level.SATISFACTORY
    parts = []
    if before_leases is not None:
        parts.append(
            f"net cash of {money(-before_leases, cur)} before leases"
            if before_leases <= 0
            else f"net debt of {money(before_leases, cur)} before leases"
        )
    if r["net_debt"] is not None and nd_ebitda is not None:
        parts.append(f"net debt including leases is {times(nd_ebitda)} EBITDA")
    if cover is not None:
        parts.append(f"interest cover {times(cover)}")
    return Section("gearing", level, ("; ".join(parts) or "Limited debt data") + ".", flags=flags)


def _receivables(c: YearContext, p: YearContext | None, cur: str) -> Section:
    r = c.ratios["receivables"]
    dso = r["dso_days"]
    if r["receivables"] is None or dso is None:
        return Section(
            "receivables", Level.NOT_ASSESSED, "Receivables or revenue were not available."
        )
    rec_growth = _growth(c.figures.get("receivables"), c.figures.get("prior_receivables"))
    rev_growth = _growth(c.figures.get("revenue"), p.figures.get("revenue") if p else None)
    prior_dso = p.ratios["receivables"]["dso_days"] if p else None
    gap = None if rec_growth is None or rev_growth is None else rec_growth - rev_growth
    alerts = []
    if gap is not None and gap > 0.10:
        alerts.append("Receivables growing faster than revenue")
    if prior_dso is not None and dso - prior_dso >= 7:
        alerts.append("Days sales outstanding up by a week or more")
    flags = list(alerts)
    if r["allowance_to_receivables"] is None:
        flags.append("Allowance for credit losses and aging not disclosed in the data")
    if dso > 120 or (gap is not None and gap > 0.50):
        level = Level.WEAK
    elif alerts:
        level = Level.NEEDS_ATTENTION
    else:
        level = Level.SATISFACTORY
    why = f"Receivables are {money(r['receivables'], cur)}, {dso:.1f} days of revenue"
    if prior_dso is not None:
        why += f" (was {prior_dso:.1f})"
    if gap is not None:
        why += f"; receivables grew {pct(rec_growth)} against revenue growth of {pct(rev_growth)}"
    why += ". No aging schedule is disclosed."
    return Section("receivables", level, why, flags=flags)


def _cash_flow(c: YearContext, p: YearContext | None, cur: str) -> Section:
    r = c.ratios["cash_flow"]
    ocf, conv, after = (
        r["operating_cash_flow"],
        r["ocf_to_net_income"],
        r["fcf_after_distributions"],
    )
    if ocf is None:
        return Section("cash_flow", Level.NOT_ASSESSED, "Operating cash flow was not available.")
    prior_ocf = p.ratios["cash_flow"]["operating_cash_flow"] if p else None
    drop = None if prior_ocf is None or prior_ocf <= 0 else 1 - ocf / prior_ocf
    flags = []
    if conv is not None and conv < 1.0:
        flags.append("Operating cash flow below net income")
    if after is not None and after < 0:
        flags.append("Free cash flow does not cover dividends and buybacks")
    if drop is not None and drop > 0.20:
        flags.append("Operating cash flow fell by more than a fifth")
    if ocf <= 0 or (conv is not None and conv < 0.5):
        level = Level.WEAK
    elif flags:
        level = Level.NEEDS_ATTENTION
    elif (
        conv is not None
        and conv >= 1.1
        and (after is None or after >= 0)
        and (drop is None or drop <= 0.10)
    ):
        level = Level.STRONG
    else:
        level = Level.SATISFACTORY
    why = f"Operating cash flow {money(ocf, cur)}"
    if drop is not None:
        why += f", {'down' if drop > 0 else 'up'} {abs(drop) * 100:.1f}% on the year before"
    if conv is not None:
        why += f", {times(conv)} net income"
    if r["free_cash_flow"] is not None:
        why += f"; free cash flow {money(r['free_cash_flow'], cur)}"
    if after is not None:
        why += f", {money(after, cur)} after dividends and buybacks"
    return Section("cash_flow", level, why + ".", flags=flags)


_RULES = {
    "balance_sheet": _balance,
    "liquidity": _liquidity,
    "gearing": _gearing,
    "receivables": _receivables,
    "cash_flow": _cash_flow,
}


def assess_year(c: YearContext, p: YearContext | None, currency: str = "USD") -> dict[str, Section]:
    return {key: rule(c, p, currency) for key, rule in _RULES.items()}


def assess(years: list[YearContext], currency: str = "USD") -> dict[str, Section]:
    """`years` is newest first. Trend compares each section with the same rules applied one year back."""
    current = assess_year(years[0], years[1] if len(years) > 1 else None, currency)
    if len(years) > 1:
        before = assess_year(years[1], years[2] if len(years) > 2 else None, currency)
        for key, section in current.items():
            earlier = before[key].level
            if section.level is Level.NOT_ASSESSED or earlier is Level.NOT_ASSESSED:
                continue
            delta = RANK[section.level] - RANK[earlier]
            section.trend = "Improving" if delta > 0 else "Weakening" if delta < 0 else "Stable"
    return current


def consolidated(sections: dict[str, Section]) -> tuple[Level, str]:
    """Policy v1.0: weak only when the core sections are weak together; strong only when all are."""
    core = [sections[key].level for key in CORE]
    assessed = [level for level in core if level is not Level.NOT_ASSESSED]
    if not assessed:
        return Level.NOT_ASSESSED, "The core sections could not be assessed."
    weak = sum(level is Level.WEAK for level in core)
    if weak >= 3:
        return Level.WEAK, f"{weak} of the 4 core sections are weak."
    if all(level is Level.STRONG for level in core):
        return Level.STRONG, "All four core sections are strong."
    return Level.SATISFACTORY, "The core sections are not weak together."


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
    attention = [s for s in sections.values() if s.level is Level.NEEDS_ATTENTION]
    weak = [s for s in sections.values() if s.level is Level.WEAK]
    missing_sections = [s for s in sections.values() if s.level is Level.NOT_ASSESSED]
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
