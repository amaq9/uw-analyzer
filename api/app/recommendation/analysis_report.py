"""The analyst's written-up analysis that travels with a draft (shown as Step 1 in the UI).

It follows the financial-statement-assessment method: scope, the five areas with their figures, the
red-flag checklist, a closing credit-style view, and the other research checks. It describes the
evidence for the underwriter; it carries no outcome, amount or number that reads as a score.

Each financial area has a **status** in three words (ADR 0018, which amends ADR 0004 for this
report only): OK, WEAK or DISTRESSED, or NOT_ASSESSED when the data is missing. The UI shows the
word beside a colour, never the colour alone. The status is derived on the server from the
analyzer's finding (strong or satisfactory = OK, needs attention = WEAK, weak = DISTRESSED)."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.ratings.schemas import PublishedRatingOut

Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
Status = Literal["OK", "WEAK", "DISTRESSED", "NOT_ASSESSED"]


class Metric(BaseModel):
    """One figure with this period, the period before, and which way it moved."""

    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, StringConstraints(max_length=80)]
    current: Annotated[str, StringConstraints(max_length=40)]
    prior: Annotated[str, StringConstraints(max_length=40)]
    earlier: Annotated[str, StringConstraints(max_length=40)] = "No earlier year"
    change: Literal["up", "down", "flat", "unknown"]
    # The framework's own reference range, indicative only (no verified peer data is used).
    reference: Annotated[str, StringConstraints(max_length=60)] = ""


class AreaReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Annotated[str, StringConstraints(max_length=40)]
    title: Annotated[str, StringConstraints(max_length=80)]
    status: Status
    finding: Annotated[str, StringConstraints(max_length=40)]  # the analyzer's own word
    trend: Annotated[str, StringConstraints(max_length=60)]
    why: Line
    flags: list[Line] = Field(default_factory=list, max_length=10)
    metrics: list[Metric] = Field(default_factory=list, max_length=14)
    # Context areas (profitability, efficiency) are shown for the underwriter but never change the
    # draft amount or outcome; the policy reads the five core areas only.
    feeds_draft: bool = True


class FlagCheck(BaseModel):
    """One item of the skill's red-flag checklist. A prompt for attention, never a pass or fail."""

    model_config = ConfigDict(extra="forbid")

    text: Line
    state: Literal["TRIGGERED", "CLEAR", "NOT_ASSESSABLE"]
    detail: Line


class OtherCheck(BaseModel):
    """A research area other than the financial statements, and what was done in it."""

    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, StringConstraints(max_length=80)]
    state: Literal["CLEAR", "FOUND", "NOT_SEARCHED", "INCOMPLETE", "NOT_ASSESSED"]
    detail: Line


class StressRow(BaseModel):
    """What the figures look like if revenue falls and costs do not. Arithmetic, not a forecast."""

    model_config = ConfigDict(extra="forbid")

    scenario: Annotated[str, StringConstraints(max_length=80)]
    earnings: Annotated[str, StringConstraints(max_length=40)]
    interest_cover: Annotated[str, StringConstraints(max_length=40)]
    cash_from_operations: Annotated[str, StringConstraints(max_length=40)]


class Basis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statements: Line
    periods: list[str] = Field(default_factory=list, max_length=5)
    currency: Annotated[str, StringConstraints(max_length=10)]
    units: Annotated[str, StringConstraints(max_length=60)]
    audit_note: Line
    method: Line


class AnalysisReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basis: Basis
    executive_summary: Line
    areas: list[AreaReport] = Field(max_length=10)
    consolidated_status: Status
    consolidated_finding: Annotated[str, StringConstraints(max_length=40)]
    consolidated_why: Line
    red_flags: list[FlagCheck] = Field(max_length=30)
    debt_service: list[Metric] = Field(default_factory=list, max_length=10)
    debt_service_notes: list[Line] = Field(default_factory=list, max_length=10)
    stress: list[StressRow] = Field(default_factory=list, max_length=4)
    stress_note: Line | None = None
    key_concerns: list[Line] = Field(default_factory=list, max_length=15)
    # Agency opinions recorded on the case when this draft was prepared. Information only: they
    # never change the outcome or the amount (ADR 0020).
    published_ratings: list[PublishedRatingOut] = Field(default_factory=list, max_length=3)
    ratings_reconciliation: Line | None = None
    strengths: list[Line] = Field(default_factory=list, max_length=12)
    weaknesses: list[Line] = Field(default_factory=list, max_length=12)
    watch: list[Line] = Field(default_factory=list, max_length=20)
    gaps: list[Line] = Field(default_factory=list, max_length=30)
    other_checks: list[OtherCheck] = Field(default_factory=list, max_length=12)
    analyzer_version: Annotated[str, StringConstraints(max_length=20)]
