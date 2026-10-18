"""The agencies' own grade scales, so a recorded grade can be checked and read correctly.

Investment grade means Moody's Aaa to Baa3 and S&P or Fitch AAA to BBB-. Anything below that is
speculative grade. (A framework text supplied to the project stops investment grade a notch
too early, at A3 and A-; the agencies' published scales are used here.)"""

from typing import Literal

Agency = Literal["MOODYS", "SP", "FITCH"]

AGENCY_NAMES: dict[str, str] = {"MOODYS": "Moody's", "SP": "S&P", "FITCH": "Fitch"}

_MOODYS = (
    "Aaa", "Aa1", "Aa2", "Aa3", "A1", "A2", "A3", "Baa1", "Baa2", "Baa3",
    "Ba1", "Ba2", "Ba3", "B1", "B2", "B3", "Caa1", "Caa2", "Caa3", "Ca", "C",
)  # fmt: skip
_LETTER_SCALE = (
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C",
)  # fmt: skip
_DEFAULT_GRADES = {"SP": ("SD", "D"), "FITCH": ("RD", "D")}
INVESTMENT_GRADE_COUNT = 10  # the first ten steps of each scale

SCALES: dict[str, tuple[str, ...]] = {
    "MOODYS": _MOODYS,
    "SP": _LETTER_SCALE + _DEFAULT_GRADES["SP"],
    "FITCH": _LETTER_SCALE + _DEFAULT_GRADES["FITCH"],
}


def normalise_grade(agency: str, grade: str) -> str | None:
    """The grade as the agency writes it, or None if it is not on that agency's scale."""
    text = grade.strip()
    for known in SCALES[agency]:
        if text == known or text.upper() == known.upper():
            return known
    return None


def is_investment_grade(agency: str, grade: str) -> bool:
    scale = SCALES[agency]
    return scale.index(grade) < INVESTMENT_GRADE_COUNT
