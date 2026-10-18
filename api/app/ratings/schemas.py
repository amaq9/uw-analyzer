"""A published agency opinion on the company, recorded with where it was read.

This is the agency's own opinion, recorded by a named person or analyst session. It is external
information for the underwriter: never this product's rating, never an input to the draft outcome or
amount. A record needs its source address, the date it was read and the quoted words (P-01,
P-02); the system never invents or infers one."""

import re
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.ratings.scale import Agency, is_agency_site, is_investment_grade, normalise_grade

_HTTPS = re.compile(r"^https://[^\s/]+\S*$")
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Outlook = Literal["STABLE", "POSITIVE", "NEGATIVE", "DEVELOPING", "NOT_STATED"]
Change = Literal["UPGRADE", "DOWNGRADE", "AFFIRMED", "NEW", "NOT_STATED"]

NOTICE = (
    "An agency's published opinion, recorded with its source. It is not this product's rating "
    "and does not change the draft."
)


class PublishedRatingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agency: Agency
    grade: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10)]
    outlook: Outlook = "NOT_STATED"
    under_review: bool = False
    change: Change = "NOT_STATED"
    last_action_on: date | None = None
    rationale: Annotated[Text, StringConstraints(max_length=600)] | None = None
    source_url: Annotated[str, StringConstraints(max_length=500)]
    retrieved_at: datetime
    quote: Annotated[Text, StringConstraints(max_length=300)]

    @field_validator("source_url")
    @classmethod
    def _secure_address(cls, value: str) -> str:
        if not _HTTPS.fullmatch(value):
            raise ValueError("A published rating needs a secure (https) source address.")
        return value

    @field_validator("retrieved_at")
    @classmethod
    def _not_future(cls, value: datetime) -> datetime:
        stamp = value if value.tzinfo else value.replace(tzinfo=UTC)
        if stamp > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("The date and time it was read cannot be in the future.")
        return stamp

    @model_validator(mode="after")
    def _agency_scale(self) -> Self:
        known = normalise_grade(self.agency, self.grade)
        if known is None:
            raise ValueError(f"{self.grade!r} is not a grade on that agency's scale.")
        self.grade = known
        if self.last_action_on and self.last_action_on > datetime.now(UTC).date():
            raise ValueError("The date of the last rating action cannot be in the future.")
        return self


class PublishedRatingOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    agency: Agency
    grade: str
    investment_grade: bool
    outlook: Outlook
    under_review: bool
    change: Change
    last_action_on: date | None
    rationale: str | None
    source_url: str
    retrieved_at: datetime
    quote: str
    recorded_by: str
    recorded_at: datetime
    notice: str = NOTICE
    # Always derived from the address, never taken from input: the agency's own website is the main
    # source, anything else is a secondary source.
    source_kind: Literal["AGENCY_SITE", "OTHER"] = "OTHER"

    @model_validator(mode="after")
    def _derive_source_kind(self) -> Self:
        own = is_agency_site(self.agency, self.source_url)
        self.source_kind = "AGENCY_SITE" if own else "OTHER"
        return self


class PublishedRatingRecord(BaseModel):
    """A stored record (includes the tenant)."""

    id: uuid.UUID
    tenant_id: str
    case_id: uuid.UUID
    agency: Agency
    grade: str
    outlook: Outlook
    under_review: bool
    change: Change
    last_action_on: date | None
    rationale: str | None
    source_url: str
    retrieved_at: datetime
    quote: str
    recorded_by: str
    recorded_at: datetime


def to_out(record: PublishedRatingRecord) -> PublishedRatingOut:
    data = record.model_dump(exclude={"tenant_id"})
    return PublishedRatingOut(
        **data, investment_grade=is_investment_grade(record.agency, record.grade)
    )
