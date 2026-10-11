"""Research report shapes (Phase 5). A report is a frozen snapshot of what the case's evidence,
claims, research runs and escalations said at one moment. It never contains a recommendation, a
score or a decision: those live elsewhere (ADR 0004, 0005)."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NOTICE = (
    "Research report for the underwriter. It reports what was found and how well it is "
    "supported. It is not an underwriting decision."
)
CONFIDENCE_RULES_VERSION = "1"


class ConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class Gate(BaseModel):
    code: str
    passed: bool
    message: str


class SourceRow(BaseModel):
    category: str
    source_key: str | None
    source_name: str | None
    state: str
    accessed: bool = Field(description="True only if an executed connector call succeeded")
    reason: str | None
    attempts: int


class ClaimRow(BaseModel):
    claim_id: uuid.UUID
    text: str
    classification: str
    material: bool
    adverse: bool
    verification_status: str
    freshness: str | None
    conflict: bool
    evidence_ids: list[uuid.UUID] = Field(description="Show-evidence links")


class EscalationRow(BaseModel):
    escalation_id: uuid.UUID
    kind: str
    state: str
    claim_id: uuid.UUID | None
    description: str
    resolution_outcome: str | None


class Counts(BaseModel):
    connector_sources_accessed: int
    documents_reviewed: int
    web_sources_recorded: int
    material_claims: int
    verified_material_findings: int
    unverified_claims: int
    information_gaps: int
    open_escalations: int
    unavailable_sources: int


class Confidence(BaseModel):
    level: ConfidenceLevel
    explanations: list[str]
    rules_version: str = CONFIDENCE_RULES_VERSION


class ReportContent(BaseModel):
    case_id: uuid.UUID
    as_of: datetime
    notice: str = NOTICE
    test_product: bool = True
    verification_log: list[SourceRow]
    material_findings: list[ClaimRow]
    unverified_claims: list[ClaimRow]
    conflicts: list[EscalationRow]
    information_gaps: list[str]
    limitations: list[str]
    adverse_search_statement: str
    evidence_confidence: Confidence
    counts: Counts
    final_statement: str


class Preview(BaseModel):
    can_complete: bool
    gates: list[Gate]
    content: ReportContent


class CompleteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
        | None
    ) = None


class ReportRecord(BaseModel):
    id: uuid.UUID
    tenant_id: str
    case_id: uuid.UUID
    version: int
    note: str | None
    content: dict[str, Any]
    content_hash: str
    versions: dict[str, Any]
    created_by: str
    created_at: datetime


class ReportSummary(BaseModel):
    id: uuid.UUID
    version: int
    note: str | None
    content_hash: str
    created_by: str
    created_at: datetime


class ReportOut(ReportSummary):
    case_id: uuid.UUID
    content: ReportContent
    versions: dict[str, Any]
    integrity_verified: bool = Field(description="The stored hash matches the stored content")
    immutable: bool = True
