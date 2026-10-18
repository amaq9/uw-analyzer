"""The analyst's written-up analysis that travels with a draft (shown as Step 1 in the UI).

It follows the financial-statement-assessment method: scope, the five areas with their figures, the
red-flag checklist, a closing credit-style view, and the other research checks. It describes the
evidence for the underwriter; it carries no outcome, amount or number that reads as a score.

Each financial area has a **status** in three words (ADR 0018, which amends ADR 0004 for this
report only): OK, WEAK or DISTRESSED, or NOT_ASSESSED when the data is missing. The UI shows the
word beside a colour, never the colour alone. The status is derived on the server from the
analyzer's finding (strong or satisfactory = OK, needs attention = WEAK, weak = DISTRESSED)."""

from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

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
    # A short paragraph on why the dimension stands where it does: the weakest measure, what is
    # better, what moved against the year before, and what it does to the proposed amount.
    summary: Annotated[str, StringConstraints(max_length=1500)] | None = None
    flags: list[Line] = Field(default_factory=list, max_length=10)
    metrics: list[Metric] = Field(default_factory=list, max_length=14)
    # Context areas (profitability, efficiency) are shown for the underwriter but never change the
    # draft amount or outcome; the policy reads the five core areas only.
    feeds_draft: bool = True


def flag_result(text: str, state: str) -> str:
    """A check's result in words: above or below its limit, or whether its condition holds."""
    if state == "NOT_ASSESSABLE":
        return "Not assessable"
    lowered = text.lower()
    if (
        " above " in lowered
        or "growing faster" in lowered
        or "large relative" in lowered
        or "down by more" in lowered
    ):
        word = "above"
    elif " below " in lowered:
        word = "below"
    else:
        return "Condition met" if state == "TRIGGERED" else "Condition not met"
    return f"{word.capitalize()} threshold" if state == "TRIGGERED" else f"Not {word} threshold"


class FlagCheck(BaseModel):
    """One item of the skill's red-flag checklist. A prompt for attention, never a pass or fail."""

    model_config = ConfigDict(extra="forbid")

    text: Line
    state: Literal["TRIGGERED", "CLEAR", "NOT_ASSESSABLE"]
    detail: Line
    # The result in words: "Above threshold" / "Not above threshold" (or below), "Condition met" /
    # "Condition not met", "Not assessable". Always derived from the check and its state.
    result: str = ""

    @model_validator(mode="after")
    def _derive_result(self) -> Self:
        self.result = flag_result(self.text, self.state)
        return self


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


class CycleRow(BaseModel):
    """One line of the cash conversion cycle, for up to three periods."""

    model_config = ConfigDict(extra="forbid")

    key: Literal["dso", "dio", "dpo", "ccc"]
    label: Annotated[str, StringConstraints(max_length=80)]
    current: Annotated[str, StringConstraints(max_length=60)]
    prior: Annotated[str, StringConstraints(max_length=60)] | None = None
    earlier: Annotated[str, StringConstraints(max_length=60)] | None = None
    movement: Annotated[str, StringConstraints(max_length=120)]
    direction: Literal["better", "worse", "same", "unknown"]


class CashCycle(BaseModel):
    """Days sales, inventory and payables outstanding, and the cash conversion cycle. Context."""

    model_config = ConfigDict(extra="forbid")

    periods: list[Annotated[str, StringConstraints(max_length=20)]] = Field(max_length=3)
    rows: list[CycleRow] = Field(max_length=4)
    summary: Line
    notes: list[Line] = Field(default_factory=list, max_length=8)
    # Rated like the financial dimensions but context only: the policy reads the core four,
    # so this never changes the amount.
    status: Status = "NOT_ASSESSED"
    finding: Annotated[str, StringConstraints(max_length=40)] = "Not assessed"
    trend: Annotated[str, StringConstraints(max_length=60)] = "No earlier year to compare"
    standing: Annotated[str, StringConstraints(max_length=1800)] | None = None
    flags: list[Line] = Field(default_factory=list, max_length=6)


class BriefSection(BaseModel):
    """One paragraph of the executive summary, under a plain heading."""

    model_config = ConfigDict(extra="forbid")

    heading: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    text: Annotated[str, StringConstraints(min_length=1, max_length=1800)]


class ExecutiveBrief(BaseModel):
    """The one-page summary for the person who decides, built from the whole analysis."""

    model_config = ConfigDict(extra="forbid")

    headline: Line
    sections: list[BriefSection] = Field(max_length=12)
    points_to_settle: list[Line] = Field(default_factory=list, max_length=8)

    @model_validator(mode="before")
    @classmethod
    def _earlier_field_name(cls, data: Any) -> Any:
        """A draft stored before the field was renamed must stay readable (drafts never change)."""
        if isinstance(data, dict) and "decision_points" in data:
            data = dict(data)
            data.setdefault("points_to_settle", data.pop("decision_points"))
            data.pop("decision_points", None)
        return data


class NoteQuote(BaseModel):
    """A sentence copied word for word from the filing."""

    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, StringConstraints(min_length=1, max_length=600)]
    where: Annotated[str, StringConstraints(max_length=80)] | None = None


class NoteFinding(BaseModel):
    """What the filing's own text says on one topic. Reported, never scored."""

    model_config = ConfigDict(extra="forbid")

    topic: Annotated[str, StringConstraints(max_length=40)]
    title: Annotated[str, StringConstraints(max_length=80)]
    state: Literal["CONCERN", "NO_CONCERN", "INFO", "NOT_FOUND"]
    summary: Line
    quotes: list[NoteQuote] = Field(default_factory=list, max_length=3)


class NotesReview(BaseModel):
    """The printed 10-K (notes and auditor's report) read for what the figures cannot show."""

    model_config = ConfigDict(extra="forbid")

    source: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    url: Annotated[str, StringConstraints(max_length=500)] | None = None
    filed: Annotated[str, StringConstraints(max_length=20)] | None = None
    sha256: Annotated[str, StringConstraints(min_length=64, max_length=64)]
    characters: int = Field(ge=0)
    summary: Line
    findings: list[NoteFinding] = Field(default_factory=list, max_length=20)


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
    # How the figures were defined (EBIT, EBITDA, net debt, ...). Method, not missing information.
    definitions: list[Line] = Field(default_factory=list, max_length=20)
    # What the filing's notes and auditor's report say, when the printed filing was read.
    notes_review: NotesReview | None = None
    cash_cycle: CashCycle | None = None
    executive_brief: ExecutiveBrief | None = None
    other_checks: list[OtherCheck] = Field(default_factory=list, max_length=12)
    analyzer_version: Annotated[str, StringConstraints(max_length=20)]
