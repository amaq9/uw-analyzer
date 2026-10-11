"""Research report endpoints (Phase 5). Anyone who can read the case can preview the report and see
which completion gates pass. Completing needs `report:complete`; it stores an immutable, hashed
version (P-08). A later completion makes a new version; earlier ones are never changed."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.evidence.router import claim_out
from app.evidence.store import PostgresEvidenceStore
from app.reports.builder import build
from app.reports.schemas import (
    CompleteIn,
    Preview,
    ReportContent,
    ReportOut,
    ReportRecord,
    ReportSummary,
)
from app.reports.store import PostgresReportStore, hash_content

router = APIRouter(prefix="/cases", tags=["reports"])


def _store(request: Request) -> PostgresReportStore:
    store: PostgresReportStore = request.app.state.report_store
    return store


def _out(record: ReportRecord) -> ReportOut:
    return ReportOut(
        id=record.id,
        version=record.version,
        note=record.note,
        content_hash=record.content_hash,
        created_by=record.created_by,
        created_at=record.created_at,
        case_id=record.case_id,
        content=ReportContent(**record.content),
        versions=record.versions,
        integrity_verified=hash_content(record.content) == record.content_hash,
    )


def _preview(request: Request, principal: Principal, case_id: uuid.UUID) -> Preview:
    case = load_case_for(request, principal, case_id)
    evidence: PostgresEvidenceStore = request.app.state.evidence_store
    claims = [claim_out(request, c) for c in evidence.list_claims(case_id, principal.tenant_id)]
    content, gates, _ = build(request, case, claims)
    return Preview(can_complete=all(g.passed for g in gates), gates=gates, content=content)


@router.get("/{case_id}/report-preview", response_model=Preview)
def preview_report(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> Preview:
    """The report as it would be written now, and which completion gates pass. Nothing is saved."""
    return _preview(request, principal, case_id)


@router.post("/{case_id}/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def complete_report(
    request: Request,
    case_id: uuid.UUID,
    body: CompleteIn,
    principal: Principal = Depends(require_permission(Permission.REPORT_COMPLETE)),  # noqa: B008
) -> ReportOut:
    """Complete the report: check every gate on the server, then store an immutable new version."""
    case = load_case_for(request, principal, case_id)
    evidence: PostgresEvidenceStore = request.app.state.evidence_store
    claims = [claim_out(request, c) for c in evidence.list_claims(case_id, principal.tenant_id)]
    content, gates, versions = build(request, case, claims)
    failed = [g for g in gates if not g.passed]
    if failed:
        record_event(
            request,
            Action.REPORT_BLOCKED,
            Outcome.DENIED,
            tenant_id=principal.tenant_id,
            actor=principal.subject,
            resource_type="case",
            resource_id=str(case_id),
            details={"failed_gates": ",".join(g.code for g in failed)},
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The report cannot be completed yet: " + " ".join(g.message for g in failed),
        )
    record = _store(request).add(
        case_id=case_id,
        tenant_id=principal.tenant_id,
        note=body.note,
        content=content.model_dump(mode="json"),
        versions=versions,
        created_by=principal.subject,
    )
    record_event(
        request,
        Action.REPORT_COMPLETED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        details={"report_id": str(record.id), "version": str(record.version)},
    )
    return _out(record)


@router.get("/{case_id}/reports", response_model=list[ReportSummary])
def list_reports(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[ReportSummary]:
    """Version history, newest first."""
    load_case_for(request, principal, case_id)
    return [
        ReportSummary(**r.model_dump(include=set(ReportSummary.model_fields)))
        for r in _store(request).list_for_case(case_id, principal.tenant_id)
    ]


@router.get("/{case_id}/reports/{version}", response_model=ReportOut)
def get_report(
    request: Request,
    case_id: uuid.UUID,
    version: int,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> ReportOut:
    load_case_for(request, principal, case_id)
    record = _store(request).get(case_id, version)
    if record is None or record.tenant_id != principal.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report version not found.")
    return _out(record)
