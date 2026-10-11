"""Confirmed financial statement figures (uploaded by a person, checked line by line by a person)."""

import math
import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.statements.extract import METRIC_LABELS

UNIT_TO_MILLIONS = {"units": 1e-6, "thousands": 1e-3, "millions": 1.0}


class Unit(StrEnum):
    UNITS = "units"
    THOUSANDS = "thousands"
    MILLIONS = "millions"


class AuditStatus(StrEnum):
    AUDITED = "AUDITED"
    REVIEWED = "REVIEWED"
    UNAUDITED = "UNAUDITED"


class MetricInfo(BaseModel):
    metric: str
    label: str


class RowOut(BaseModel):
    metric: str
    label: str = Field(description="The line label exactly as found in the document")
    values: list[float | None]


class ExtractionOut(BaseModel):
    document_id: uuid.UUID
    filename: str
    periods: list[str]
    period_end_guesses: list[str | None]
    unit_guess: Unit | None
    currency_guess: str | None
    rows: list[RowOut]
    notes: list[str]
    metrics: list[MetricInfo]
    notice: str = (
        "These are suggestions read from the file. Check every figure against the document, correct it if "
        "needed, and confirm. Nothing is used until you confirm."
    )


class PeriodIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_end: date
    figures: dict[str, float | None]

    @field_validator("figures")
    @classmethod
    def _known_and_finite(cls, value: dict[str, float | None]) -> dict[str, float | None]:
        unknown = sorted(set(value) - set(METRIC_LABELS))
        if unknown:
            raise ValueError("Unknown figure: " + ", ".join(unknown))
        if any(v is not None and not math.isfinite(v) for v in value.values()):
            raise ValueError("Figures must be ordinary numbers.")
        return value


class StatementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: uuid.UUID
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    unit: Unit
    audit_status: AuditStatus
    periods: list[PeriodIn] = Field(min_length=1, max_length=4)
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None

    @model_validator(mode="after")
    def _rules(self) -> Self:
        ends = [p.period_end for p in self.periods]
        if len(set(ends)) != len(ends):
            raise ValueError("Each period can be given once.")
        if any(end > date.today() for end in ends):
            raise ValueError("A period end cannot be in the future.")
        for p in self.periods:
            if sum(v is not None for v in p.figures.values()) < 3:
                raise ValueError("Give at least three figures for each period.")
        return self


class StatementRecord(BaseModel):
    id: uuid.UUID
    tenant_id: str
    case_id: uuid.UUID
    document_id: uuid.UUID
    period_end: date
    currency: str
    unit: Unit
    audit_status: AuditStatus
    figures: dict[str, Any]
    notes: str | None
    confirmed_by: str
    confirmed_at: datetime


class StatementOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    period_end: date
    currency: str
    unit: Unit
    audit_status: AuditStatus
    figures: dict[str, float | None]
    notes: str | None
    confirmed_by: str
    confirmed_at: datetime


def to_out(record: StatementRecord) -> StatementOut:
    return StatementOut(**record.model_dump(exclude={"tenant_id", "case_id"}))
