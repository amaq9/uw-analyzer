"""A short paragraph that says why a dimension has the standing it has.

Built only from the measures the rules already used, so the words can never disagree with the finding: it
names the weakest measure (the one that sets the rating), what it is against its reference, which measures are
better, what moved against the year before, and what the rating does to the proposed amount."""

from dataclasses import dataclass

from app.analysis.formats import days, money, pct, times

BAND_WORD = {3: "strong", 2: "adequate", 1: "concerning", 0: "critical"}
FINDING = {
    "STRONG": "Strong",
    "SATISFACTORY": "Adequate",
    "NEEDS_ATTENTION": "Concerning",
    "WEAK": "Critical",
}
STATUS = {"STRONG": "OK", "SATISFACTORY": "OK", "NEEDS_ATTENTION": "Weak", "WEAK": "Distressed"}


@dataclass
class Measure:
    """One figure a dimension is judged on. `band` is 3 strong, 2 adequate, 1 concerning, 0 critical,
    or None when the figure is shown for context and does not set the rating."""

    label: str
    value: float | None
    prior: float | None
    kind: str  # times | pct | money | points
    band: int | None
    reference: str
    higher_is_better: bool = True

    def show(self, v: float | None, currency: str) -> str:
        if v is None:
            return "not available"
        if self.kind == "times":
            return times(v)
        if self.kind == "pct":
            return pct(v)
        if self.kind == "points":
            return f"{v * 100:+.1f} points"
        if self.kind == "days":
            return days(v)
        if self.kind == "days_change":
            return f"{v:+.1f} days"
        return money(v, currency)

    def worsened(self) -> bool:
        if self.value is None or self.prior is None or self.value == self.prior:
            return False
        return (self.value < self.prior) == self.higher_is_better

    def improved(self) -> bool:
        if self.value is None or self.prior is None or self.value == self.prior:
            return False
        return (self.value > self.prior) == self.higher_is_better


def _lc(label: str) -> str:
    """Lower-case the first letter, but keep acronyms such as EBITDA."""
    return label if label[:2].isupper() else label[0].lower() + label[1:]


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def summarise(
    *,
    title: str,
    level: str,
    trend: str,
    earlier_level: str | None,
    measures: list[Measure],
    currency: str,
    cut_percent: int | None,
    core: bool,
) -> str:
    banded = [m for m in measures if m.band is not None and m.value is not None]
    if not banded:
        return ""
    worst = min(m.band for m in banded if m.band is not None)
    drivers = [m for m in banded if m.band == worst]
    rest = [m for m in measures if m not in drivers and m.value is not None]
    finding, status = FINDING[level], STATUS[level]

    def driver_text(m: Measure) -> str:
        return (
            f"{_lc(m.label)} "
            f"is {m.show(m.value, currency)}, which is {BAND_WORD[m.band or 0]} (reference: {m.reference})"
        )

    drivers_text = "; ".join(driver_text(m) for m in drivers)
    if worst == 3:
        first = (
            f"{title} is rated {finding} (shown as {status}): every rated measure is strong: "
            + _join([f"{_lc(m.label)} {m.show(m.value, currency)}" for m in drivers])
            + "."
        )
    elif worst == 2:
        first = (
            f"{title} is rated {finding} (shown as {status}): no measure is concerning, and the weakest "
            f"{'is' if len(drivers) == 1 else 'are'}: {drivers_text}."
        )
    else:
        first = (
            f"{title} is rated {finding} (shown as {status}) because it is judged by its weakest measure: "
            f"{drivers_text}."
        )
    parts = [first]
    if rest:
        shown = []
        for m in rest:
            word = f" ({BAND_WORD[m.band]})" if m.band is not None else ""
            shown.append(f"{_lc(m.label)} {m.show(m.value, currency)}{word}")
        better = worst <= 1 and all(m.band is not None and m.band > worst for m in rest)
        parts.append(
            ("The other measures are better: " if better else "Other measures: ")
            + _join(shown)
            + "."
        )
    if trend in ("Weakening", "Improving") and earlier_level is not None:
        moved = f"Against the year before the rating moved from {FINDING[earlier_level].lower()} to {finding.lower()}"
        changed = [m for m in measures if (m.worsened() if trend == "Weakening" else m.improved())]
        if changed:
            word = "worsened" if trend == "Weakening" else "improved"
            moved += f". Measures that {word}: " + "; ".join(
                f"{_lc(m.label)} {m.show(m.prior, currency)} to {m.show(m.value, currency)}"
                for m in changed[:4]
            )
        parts.append(moved + ".")
    elif trend == "Stable":
        parts.append("The rating is unchanged from the year before.")
    if core:
        parts.append(
            f"This lowers the UW Analyzer's proposed amount by {cut_percent}% of the amount requested."
            if cut_percent
            else "This does not lower the UW Analyzer's proposed amount."
        )
    return " ".join(parts)
