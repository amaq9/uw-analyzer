"""Case intake data (FR-1.1, FR-1.3). Case content is Restricted: never log it or put it in audit
details. Missing inputs become information gaps; the system never fills in a value."""

import re
import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_CURRENCY = re.compile(r"^[A-Z]{3}$")
_WEBSITE = re.compile(r"^https?://[^\s/]+\S*$")


class CaseStatus(StrEnum):
    """Phase 1 statuses. Later phases add research and review statuses."""

    DRAFT = "DRAFT"
    ENTITY_AMBIGUOUS = "ENTITY_AMBIGUOUS"
    ENTITY_RESOLVED = "ENTITY_RESOLVED"


class CaseFields(BaseModel):
    """The intake fields a user may supply. Everything is optional except that a case needs a
    legal name or a trading name. Unknown fields are rejected (no mass assignment)."""

    model_config = ConfigDict(extra="forbid")

    legal_name: str | None = Field(default=None, max_length=200)
    trading_name: str | None = Field(default=None, max_length=200)
    registration_number: str | None = Field(default=None, max_length=100)
    jurisdiction: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=500)
    industry: str | None = Field(default=None, max_length=200)
    parent_name: str | None = Field(default=None, max_length=200)
    ubo_name: str | None = Field(default=None, max_length=200)
    exposure_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    exposure_currency: str | None = Field(default=None, description="ISO 4217, e.g. CAD")
    terms: str | None = Field(default=None, max_length=2000)
    context: str | None = Field(default=None, max_length=5000)

    @field_validator("*", mode="before")
    @classmethod
    def _blank_is_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("website")
    @classmethod
    def _website_is_http(cls, value: str | None) -> str | None:
        if value is not None and not _WEBSITE.fullmatch(value):
            raise ValueError("Website must start with http:// or https://")
        return value

    @field_validator("exposure_currency")
    @classmethod
    def _currency_code(cls, value: str | None) -> str | None:
        if value is not None and not _CURRENCY.fullmatch(value):
            raise ValueError("Currency must be a 3-letter code such as CAD or USD")
        return value


def check_case_rules(fields: dict[str, Any]) -> None:
    """Cross-field rules, applied on create and again on the merged result of an update."""
    if not (fields.get("legal_name") or fields.get("trading_name")):
        raise ValueError("Provide a legal name or a trading name.")
    if (fields.get("exposure_amount") is None) != (fields.get("exposure_currency") is None):
        raise ValueError("Give the exposure amount and its currency together, or neither.")


class CaseCreate(CaseFields):
    @model_validator(mode="after")
    def _rules(self) -> Self:
        check_case_rules(self.model_dump())
        return self


class CaseUpdate(CaseFields):
    """Partial update. `expected_version` guards against overwriting someone else's change."""

    expected_version: int = Field(ge=1)


class InformationGap(BaseModel):
    field: str
    description: str


class CaseRecord(CaseFields):
    """A stored case, as the store returns it (includes the tenant, which is never sent out)."""

    id: uuid.UUID
    tenant_id: str
    owner: str
    status: CaseStatus
    version: int
    created_at: datetime
    updated_at: datetime


class CaseOut(CaseFields):
    id: uuid.UUID
    owner: str
    status: CaseStatus
    version: int
    created_at: datetime
    updated_at: datetime
    information_gaps: list[InformationGap]


# Missing material inputs are reported, never generated (FR-1.3).
_GAP_RULES: list[tuple[str, str]] = [
    ("legal_name", "Legal name not provided; entity resolution needs the exact legal entity."),
    ("registration_number", "Registration number not provided."),
    ("jurisdiction", "Jurisdiction not provided."),
    ("address", "Address not provided."),
    ("industry", "Industry not provided."),
    ("website", "Website not provided."),
    ("exposure_amount", "Requested exposure not provided."),
    ("terms", "Payment terms not provided."),
]


def information_gaps(case: CaseFields) -> list[InformationGap]:
    gaps = [
        InformationGap(field=name, description=text)
        for name, text in _GAP_RULES
        if getattr(case, name) is None
    ]
    if case.parent_name is None and case.ubo_name is None:
        gaps.append(
            InformationGap(field="ownership", description="Parent or ultimate owner not provided.")
        )
    return gaps


def to_out(record: CaseRecord) -> CaseOut:
    data = record.model_dump(exclude={"tenant_id"})
    return CaseOut(**data, information_gaps=information_gaps(record))
