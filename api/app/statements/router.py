"""Uploaded financial statements: read suggestions out of a document, let a person check and confirm
them, and keep the confirmed figures. Suggesting needs `case:write` (it opens the document); reading
the confirmed figures needs `case:read`. Confirmed figures are append-only; a newer confirmation for
a period replaces the older one for analysis, and the older one stays on record."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import assert_same_tenant, require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.documents.service import DocumentService, UploadUnavailableError
from app.statements.extract import METRIC_LABELS, UnreadableFile, extract
from app.statements.schemas import (
    ExtractionOut,
    MetricInfo,
    RowOut,
    StatementCreate,
    StatementOut,
    Unit,
    to_out,
)
from app.statements.store import PostgresStatementStore

router = APIRouter(prefix="/cases", tags=["statements"])


def _store(request: Request) -> PostgresStatementStore:
    store: PostgresStatementStore = request.app.state.statement_store
    return store


def _service(request: Request) -> DocumentService:
    service: DocumentService | None = getattr(request.app.state, "document_service", None)
    if service is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Document storage is not set up on this server."
        )
    return service


def _document(request: Request, principal: Principal, case_id: uuid.UUID, document_id: uuid.UUID):  # type: ignore[no-untyped-def]
    service = _service(request)
    load_case_for(request, principal, case_id)
    record = service.store.get(document_id)
    if record is None or record.case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    assert_same_tenant(
        request, principal, record.tenant_id, resource_type="document", resource_id=str(document_id)
    )
    return service, record


@router.get("/{case_id}/documents/{document_id}/figures-preview", response_model=ExtractionOut)
def preview_figures(
    request: Request,
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_WRITE)),  # noqa: B008
) -> ExtractionOut:
    """Suggest figures found in the document. Nothing is saved or used."""
    service, record = _document(request, principal, case_id, document_id)
    try:
        data = b"".join(service.open(record))
    except UploadUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The document could not be read right now. Try again shortly.",
        ) from None
    try:
        found = extract(record.filename, record.content_type, data)
    except UnreadableFile as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return ExtractionOut(
        document_id=document_id,
        filename=record.filename,
        periods=found.period_labels,
        period_end_guesses=found.period_end_guesses,
        unit_guess=Unit(found.unit_guess) if found.unit_guess else None,
        currency_guess=found.currency_guess,
        rows=[RowOut(metric=r.metric, label=r.label, values=r.values) for r in found.rows],
        notes=found.notes,
        metrics=[MetricInfo(metric=k, label=v) for k, v in METRIC_LABELS.items()],
    )


@router.post(
    "/{case_id}/statements", response_model=list[StatementOut], status_code=status.HTTP_201_CREATED
)
def confirm_statements(
    request: Request,
    case_id: uuid.UUID,
    body: StatementCreate,
    principal: Principal = Depends(require_permission(Permission.CASE_WRITE)),  # noqa: B008
) -> list[StatementOut]:
    """A named person confirms the figures for one or more periods of an uploaded document."""
    _document(request, principal, case_id, body.document_id)
    records = _store(request).add_all(
        tenant_id=principal.tenant_id,
        case_id=case_id,
        document_id=body.document_id,
        currency=body.currency,
        unit=body.unit,
        audit_status=body.audit_status,
        periods=[
            (p.period_end, {k: v for k, v in p.figures.items() if v is not None})
            for p in body.periods
        ],
        notes=body.notes,
        confirmed_by=principal.subject,
    )
    record_event(
        request,
        Action.STATEMENT_CONFIRMED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        details={"document_id": str(body.document_id), "periods": str(len(records))},
    )
    return [to_out(r) for r in records]


@router.get("/{case_id}/statements", response_model=list[StatementOut])
def list_statements(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[StatementOut]:
    """The confirmed figures in use, newest period first."""
    load_case_for(request, principal, case_id)
    return [to_out(r) for r in _store(request).latest_per_period(case_id, principal.tenant_id)]
