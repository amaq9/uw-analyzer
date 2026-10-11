"""Research run and plan shapes. A run records the versions it was made with (P-10). The plan states
what would be searched and what cannot be; it never says a source was accessed (FR-2.7)."""

import re
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.research.plan import Category, StepState

_JURISDICTION = re.compile(r"^[A-Z]{2}$")


class RunStatus(StrEnum):
    PLANNED = "PLANNED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jurisdictions: list[str] = Field(
        min_length=1,
        max_length=20,
        description="Countries to cover: the entity's, its parent's and where it operates "
        "(ISO 3166-1 alpha-2)",
    )
    idempotency_key: Annotated[str, Field(min_length=8, max_length=100)] | None = None

    @field_validator("jurisdictions")
    @classmethod
    def _valid(cls, value: list[str]) -> list[str]:
        cleaned = sorted({v.strip().upper() for v in value})
        if any(not _JURISDICTION.fullmatch(v) for v in cleaned):
            raise ValueError("Jurisdictions are two-letter country codes, for example CA.")
        return cleaned


class StepOut(BaseModel):
    id: uuid.UUID
    ordinal: int
    category: Category
    state: StepState
    reason: str | None
    discovery_only: bool
    source_id: uuid.UUID | None
    source: dict[str, Any]
    attempts: int
    max_attempts: int
    error_class: str | None
    started_at: datetime | None
    finished_at: datetime | None
    accessed: bool = Field(
        default=False,
        description="True only if an executed connector call returned a provenance reference. "
        "This is not verification.",
    )


class RunOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    status: RunStatus
    trigger: str
    jurisdictions: list[str]
    versions: dict[str, Any]
    correlation_id: str
    created_by: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    steps: list[StepOut]
    notice: str = (
        "A plan says what would be searched and what cannot be. Nothing here shows that a "
        "source was accessed or that a claim is verified."
    )


class RunRecord(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    tenant_id: str
    status: RunStatus
    trigger: str
    jurisdictions: list[str]
    versions: dict[str, Any]
    idempotency_key: str | None
    correlation_id: str
    created_by: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class StepRecord(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    ordinal: int
    category: Category
    state: StepState
    reason: str | None
    discovery_only: bool
    source_id: uuid.UUID | None
    source_snapshot: dict[str, Any]
    attempts: int
    max_attempts: int
    error_class: str | None
    started_at: datetime | None
    finished_at: datetime | None


class CallRecord(BaseModel):
    id: uuid.UUID
    tenant_id: str
    case_id: uuid.UUID
    run_id: uuid.UUID
    step_id: uuid.UUID
    source_id: uuid.UUID
    source_key: str
    connector_version: str
    attempt: int
    action: str
    access_status: str
    started_at: datetime
    ended_at: datetime
    outcome: str
    error_class: str | None
    provenance_ref: str | None


class CallOut(BaseModel):
    """One executed connector call. This log, not any model output, is what shows a source was
    accessed (FR-2.6, FR-2.7)."""

    id: uuid.UUID
    step_id: uuid.UUID
    source_key: str
    connector_version: str
    attempt: int
    action: str
    access_status: str
    started_at: datetime
    ended_at: datetime
    outcome: str
    error_class: str | None
    provenance_ref: str | None


def call_out(call: CallRecord) -> CallOut:
    return CallOut(**call.model_dump(include=set(CallOut.model_fields)))


def to_out(run: RunRecord, steps: list[StepRecord], accessed: set[uuid.UUID]) -> RunOut:
    return RunOut(
        **run.model_dump(exclude={"tenant_id", "idempotency_key"}),
        steps=[
            StepOut(
                **s.model_dump(exclude={"run_id", "source_snapshot"}),
                source=s.source_snapshot,
                accessed=s.id in accessed,
            )
            for s in steps
        ],
    )
