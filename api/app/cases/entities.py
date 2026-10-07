"""Entity candidates and the ambiguity stop (FR-1.4 to FR-1.6, P-03, AC-01, BR-01).

Candidates are entered by a person: the system never invents one (P-02). Two or more open
candidates make a case ENTITY_AMBIGUOUS. Only an explicit human action resolves it (P-07).
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.cases.schemas import _WEBSITE, CaseStatus

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CandidateState(StrEnum):
    CANDIDATE = "candidate"
    SELECTED = "selected"
    REJECTED = "rejected"


class CandidateCreate(BaseModel):
    """A plausible legal entity for the case. Only the legal name is required."""

    model_config = ConfigDict(extra="forbid")

    legal_name: Name
    registration_number: str | None = Field(default=None, max_length=100)
    jurisdiction: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=500)
    parent_name: str | None = Field(default=None, max_length=200)
    aliases: list[Name] = Field(default_factory=list, max_length=20)
    former_names: list[Name] = Field(default_factory=list, max_length=20)
    subsidiaries: list[Name] = Field(default_factory=list, max_length=50)

    @field_validator(
        "registration_number", "jurisdiction", "address", "website", "parent_name", mode="before"
    )
    @classmethod
    def _blank_is_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("website")
    @classmethod
    def _website_is_http(cls, value: str | None) -> str | None:
        if value is not None and not _WEBSITE.fullmatch(value):
            raise ValueError("Website must start with http:// or https://")
        return value


class CandidateOut(CandidateCreate):
    id: uuid.UUID
    case_id: uuid.UUID
    state: CandidateState
    source: str
    created_by: str
    created_at: datetime


class ResolveRequest(BaseModel):
    """The human choice of the one exact legal entity."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note", mode="before")
    @classmethod
    def _blank_note(cls, value: Any) -> Any:
        return (value.strip() or None) if isinstance(value, str) else value


class ReopenRequest(BaseModel):
    """Reopening a resolved entity is an override, so a reason is mandatory."""

    model_config = ConfigDict(extra="forbid")

    reason: Name = Field(max_length=1000)


class Blocker(BaseModel):
    code: str
    message: str


class Readiness(BaseModel):
    allowed: bool
    status: CaseStatus
    blockers: list[Blocker]


class ResearchBlockedError(Exception):
    """Raised when something tries to start substantive research on an unresolved entity."""

    def __init__(self, readiness: Readiness) -> None:
        super().__init__("research is blocked")
        self.readiness = readiness


def research_readiness(status: CaseStatus, open_candidates: int) -> Readiness:
    """Whether substantive research may start, and if not, what a person must do (AC-01)."""
    if status is CaseStatus.ENTITY_RESOLVED:
        return Readiness(allowed=True, status=status, blockers=[])
    if status is CaseStatus.ENTITY_AMBIGUOUS:
        blocker = Blocker(
            code="entity_ambiguous",
            message=(
                f"{open_candidates} legal entities could match. Research cannot start until a "
                "person chooses the one exact legal entity."
            ),
        )
    elif open_candidates == 0:
        blocker = Blocker(
            code="entity_not_identified",
            message="No legal entity has been identified yet. Add the candidate legal "
            "entity, then confirm it.",
        )
    else:
        blocker = Blocker(
            code="entity_not_confirmed",
            message="A legal entity has been added but not yet confirmed. A person must "
            "confirm it before research can start.",
        )
    return Readiness(allowed=False, status=status, blockers=[blocker])


def require_research_allowed(readiness: Readiness) -> None:
    """Server-side gate for every research start, now and in later phases. Never skippable."""
    if not readiness.allowed:
        raise ResearchBlockedError(readiness)
