"""How amounts, multiples and percentages are written in the analysis, in one place."""

from decimal import ROUND_HALF_UP, Decimal


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


def days(x: float | None) -> str:
    return "not calculable" if x is None else f"{x:.1f} days"
