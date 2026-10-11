"""Source and connector registry data (FR-2.1, FR-2.2). The registry says what the product is
CAPABLE of reaching. It is never proof that a source was accessed: only a recorded connector call
is (FR-2.6, FR-2.7). Credentials are never stored or returned here."""

import re
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{1,59}$")
_JURISDICTION = re.compile(r"^([A-Z]{2}|GLOBAL)$")


class SourceClass(StrEnum):
    OFFICIAL = "OFFICIAL"
    COMMERCIAL = "COMMERCIAL"
    SECONDARY = "SECONDARY"
    WEAK = "WEAK"


class AccessCategory(StrEnum):
    ACTUALLY_ACCESSIBLE = "ACTUALLY_ACCESSIBLE"
    RESTRICTED_LICENSED = "RESTRICTED_LICENSED"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"
    TECHNICALLY_UNAVAILABLE = "TECHNICALLY_UNAVAILABLE"


class AuthState(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    CONFIGURED = "CONFIGURED"
    MISSING = "MISSING"


class Health(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


class SourceFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    source_class: SourceClass
    source_type: str = Field(
        min_length=1, max_length=80, description="e.g. company_registry, court_records, news"
    )
    jurisdictions: list[str] = Field(
        min_length=1, max_length=60, description="ISO 3166-1 alpha-2 codes, or GLOBAL"
    )
    access_category: AccessCategory
    auth_state: AuthState
    terms_notes: str | None = Field(default=None, max_length=2000)
    rate_limit_per_minute: int | None = Field(default=None, gt=0, le=100_000)

    @field_validator("name", "source_type", "terms_notes", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() or None if isinstance(value, str) else value

    @field_validator("jurisdictions")
    @classmethod
    def _jurisdictions_valid(cls, value: list[str]) -> list[str]:
        cleaned = sorted({v.strip().upper() for v in value})
        if any(not _JURISDICTION.fullmatch(v) for v in cleaned):
            raise ValueError("Jurisdictions are two-letter country codes (e.g. CA) or GLOBAL.")
        return cleaned

    @model_validator(mode="after")
    def _accessible_needs_credentials(self) -> Self:
        if (
            self.access_category is AccessCategory.ACTUALLY_ACCESSIBLE
            and self.auth_state is AuthState.MISSING
        ):
            raise ValueError(
                "A source that needs a credential we do not hold cannot be marked "
                "ACTUALLY_ACCESSIBLE."
            )
        return self


class SourceCreate(SourceFields):
    key: str = Field(description="Stable lowercase identifier, unique per tenant")

    @field_validator("key")
    @classmethod
    def _key_valid(cls, value: str) -> str:
        if not _KEY.fullmatch(value):
            raise ValueError(
                "Key is 2 to 60 characters: lowercase letters, digits, hyphen or underscore."
            )
        return value


class SourceUpdate(BaseModel):
    """Any subset of the fields, plus the version the caller last saw."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    source_class: SourceClass | None = None
    source_type: str | None = Field(default=None, min_length=1, max_length=80)
    jurisdictions: list[str] | None = Field(default=None, min_length=1, max_length=60)
    access_category: AccessCategory | None = None
    auth_state: AuthState | None = None
    terms_notes: str | None = Field(default=None, max_length=2000)
    rate_limit_per_minute: int | None = Field(default=None, gt=0, le=100_000)
    health: Health | None = None


class SourceRecord(BaseModel):
    id: uuid.UUID
    tenant_id: str
    key: str
    name: str
    source_class: SourceClass
    source_type: str
    jurisdictions: list[str]
    access_category: AccessCategory
    auth_state: AuthState
    terms_notes: str | None
    rate_limit_per_minute: int | None
    health: Health
    health_checked_at: datetime | None
    version: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class SourceOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    source_class: SourceClass
    source_type: str
    jurisdictions: list[str]
    access_category: AccessCategory
    auth_state: AuthState
    terms_notes: str | None
    rate_limit_per_minute: int | None
    health: Health
    health_checked_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    notice: str = (
        "Registry entry: what the product can reach. It is not proof that a source was accessed."
    )


def to_out(record: SourceRecord) -> SourceOut:
    return SourceOut(**record.model_dump(exclude={"tenant_id", "created_by"}))
