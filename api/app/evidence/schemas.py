"""Evidence and claim shapes (FR-3.1 to FR-3.5, FR-3.8). Access (when and how a source was read) and
verification (what the evidence supports) are separate fields and are never merged (P-04)."""

import re
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.evidence.rules import (
    Classification,
    EvidenceType,
    Freshness,
    Relation,
    VerificationStatus,
)

_HTTPS = re.compile(r"^https://[^\s/]+\S*$")
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
SourceClassName = Literal["OFFICIAL", "COMMERCIAL", "SECONDARY", "WEAK"]
ClaimCategory = Literal[
    "ENTITY_REGISTRY", "FINANCIALS", "ADVERSE_SEARCH", "COUNTRY_INDUSTRY", "OTHER"
]


class EvidenceCreate(BaseModel):
    """What a person or session may submit. For connector evidence the server derives the source,
    class, provenance and discovery flag from the logged call; the author cannot set them."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["DOCUMENT", "CONNECTOR", "WEB"]
    evidence_type: EvidenceType
    title: Annotated[Text, StringConstraints(max_length=300)]
    origin: Annotated[Text, StringConstraints(max_length=200, to_lower=True)] = Field(
        description="Who published it (organisation or domain). Different origins count as "
        "independent."
    )
    excerpt: Annotated[Text, StringConstraints(max_length=1000)]
    is_primary: bool = Field(
        default=False, description="The originating record itself, not a report about it"
    )
    published_on: date | None = None
    event_on: date | None = None
    content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_class: SourceClassName | None = None  # documents and web only
    document_id: uuid.UUID | None = None
    connector_call_id: uuid.UUID | None = None
    url: str | None = Field(default=None, max_length=500)
    retrieved_at: datetime | None = None

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.kind == "CONNECTOR":
            if not self.connector_call_id:
                raise ValueError("Connector evidence needs the id of the logged connector call.")
            if self.source_class or self.document_id or self.retrieved_at:
                raise ValueError(
                    "Connector evidence takes its class and access time from the call log."
                )
        else:
            if self.source_class is None:
                raise ValueError("Say what kind of source it is (official, commercial, ...).")
            if self.connector_call_id:
                raise ValueError("Only connector evidence refers to a connector call.")
        if self.kind == "DOCUMENT":
            if not self.document_id:
                raise ValueError("Document evidence needs the document id.")
            if self.url or self.retrieved_at:
                raise ValueError("Document evidence must not carry a web address.")
        if self.kind == "WEB":
            if not (self.url and _HTTPS.fullmatch(self.url)):
                raise ValueError("Web evidence needs a secure (https) address.")
            if self.retrieved_at is None:
                raise ValueError("Web evidence needs the date and time it was read.")
            if self.document_id:
                raise ValueError("Web evidence must not carry a document id.")
        return self


class EvidenceRecord(BaseModel):
    id: uuid.UUID
    tenant_id: str
    case_id: uuid.UUID
    kind: str
    evidence_type: EvidenceType
    source_class: str
    class_basis: str
    source_id: uuid.UUID | None
    connector_call_id: uuid.UUID | None
    document_id: uuid.UUID | None
    title: str
    origin: str
    url: str | None
    published_on: date | None
    event_on: date | None
    accessed_at: datetime
    excerpt: str
    provenance_ref: str | None
    content_hash: str | None
    is_primary: bool
    discovery_only: bool
    created_by: str
    created_at: datetime


class EvidenceOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    kind: str
    evidence_type: EvidenceType
    source_class: str
    source_class_basis: str = Field(description="registry, or author_declared")
    source_id: uuid.UUID | None
    connector_call_id: uuid.UUID | None
    document_id: uuid.UUID | None
    title: str
    origin: str
    url: str | None
    published_on: date | None
    event_on: date | None
    accessed_at: datetime
    excerpt: str
    provenance_ref: str | None
    content_hash: str | None
    is_primary: bool
    discovery_only: bool
    freshness: Freshness
    created_by: str
    created_at: datetime


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: uuid.UUID
    relation: Relation
    notes: Annotated[Text, StringConstraints(max_length=500)] | None = None


class ClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[Text, StringConstraints(max_length=1000)] = Field(
        description="The exact proposition"
    )
    classification: Classification
    material: bool
    adverse: bool = False
    credit_relevance: Annotated[Text, StringConstraints(max_length=500)] | None = None
    category: ClaimCategory | None = None
    basis_claim_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    unavailable_step_id: uuid.UUID | None = Field(
        default=None, description="A research step that could not reach the source"
    )
    evidence: list[LinkIn] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def _rules(self) -> Self:
        judgement = self.classification in (Classification.INTERPRETATION, Classification.INFERENCE)
        if judgement and self.material and not (self.basis_claim_ids or self.evidence):
            raise ValueError(
                "A material interpretation or inference must link the facts or evidence it "
                "rests on (FR-3.8)."
            )
        if self.basis_claim_ids and not judgement:
            raise ValueError("Only an interpretation or inference is based on other claims.")
        ids = [e.evidence_id for e in self.evidence]
        if len(set(ids)) != len(ids) or len(set(self.basis_claim_ids)) != len(self.basis_claim_ids):
            raise ValueError("Each evidence item and basis claim can be linked once.")
        return self


class ClaimRecord(BaseModel):
    id: uuid.UUID
    tenant_id: str
    case_id: uuid.UUID
    text: str
    classification: Classification
    material: bool
    adverse: bool
    credit_relevance: str | None
    category: str | None
    unavailable_step_id: uuid.UUID | None
    created_by: str
    created_at: datetime


class LinkRecord(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    evidence_id: uuid.UUID
    relation: Relation
    notes: str | None
    created_by: str
    created_at: datetime


class Verification(BaseModel):
    status: VerificationStatus
    reasons: list[str]
    needs: list[str]
    conflict: bool
    rules_version: str


class LinkOut(BaseModel):
    id: uuid.UUID
    relation: Relation
    notes: str | None
    evidence: EvidenceOut


class ClaimOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    text: str
    classification: Classification
    material: bool
    adverse: bool
    credit_relevance: str | None
    category: str | None
    unavailable_step_id: uuid.UUID | None
    basis_claim_ids: list[uuid.UUID]
    verification: Verification
    freshness: Freshness | None = Field(
        description="Freshness of the newest reliable supporting evidence, if any"
    )
    links: list[LinkOut]
    created_by: str
    created_at: datetime
    notice: str = (
        "Verification status is computed from the linked evidence by fixed rules; it cannot be "
        "set by a person or a model."
    )


def evidence_out(record: EvidenceRecord, fresh: Freshness) -> EvidenceOut:
    data: dict[str, Any] = record.model_dump(exclude={"tenant_id", "class_basis"})
    return EvidenceOut(**data, source_class_basis=record.class_basis, freshness=fresh)
