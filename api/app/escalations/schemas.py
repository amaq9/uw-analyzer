"""Escalations: items that need a person (P-07). Conflicts between reliable sources raise one
automatically; people can raise others. Nothing closes an escalation except a named reviewer's
written resolution."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
LABEL = "HUMAN_REVIEW_REQUIRED"


class Kind(StrEnum):
    CONFLICT = "CONFLICT"
    MATERIAL_AMBIGUITY = "MATERIAL_AMBIGUITY"
    OTHER = "OTHER"


class ResolutionOutcome(StrEnum):
    SUPPORTING_PREVAILS = "SUPPORTING_PREVAILS"
    CONTRADICTING_PREVAILS = "CONTRADICTING_PREVAILS"
    NO_CLAIM_CHANGE = "NO_CLAIM_CHANGE"


class EscalationCreate(BaseModel):
    """A person raising something for review. Conflicts are raised by the system, not here."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["MATERIAL_AMBIGUITY", "OTHER"]
    description: Annotated[Text, StringConstraints(max_length=1000)]
    claim_id: uuid.UUID | None = None


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: ResolutionOutcome
    explanation: Annotated[Text, StringConstraints(min_length=10, max_length=2000)] = Field(
        description="Why this evidence or decision was preferred"
    )
    preferred_evidence_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        decides_claim = self.outcome is not ResolutionOutcome.NO_CLAIM_CHANGE
        if decides_claim and self.preferred_evidence_id is None:
            raise ValueError("Say which evidence was preferred.")
        if not decides_claim and self.preferred_evidence_id is not None:
            raise ValueError(
                "No preferred evidence is recorded when nothing about a claim changes."
            )
        return self


class Resolution(BaseModel):
    outcome: ResolutionOutcome
    preferred_evidence_id: uuid.UUID | None
    explanation: str
    resolved_by: str
    resolved_at: datetime


class EscalationOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    kind: Kind
    label: str = LABEL
    state: Literal["OPEN", "RESOLVED"]
    claim_id: uuid.UUID | None
    description: str
    raised_by_system: bool
    created_by: str
    created_at: datetime
    resolution: Resolution | None
    comparison: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Conflicts only: each side of the dispute compared on authority, date, "
        "specificity, independence and data quality",
    )


class EscalationList(BaseModel):
    open_count: int
    items: list[EscalationOut]
