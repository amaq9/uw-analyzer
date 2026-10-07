"""Document endpoints (FR-1.2). Uploads need `case:write`; listing and downloading need `case:read`.
Everything is tenant-scoped, audited, and answers with the standard error object. File names, file
contents and storage locations never appear in audit details or logs."""

import uuid
from itertools import chain
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import assert_same_tenant, require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.documents.schemas import DocumentCategory, DocumentOut, DocumentRecord
from app.documents.service import DocumentService, UploadUnavailableError
from app.documents.validation import RejectedFileError

router = APIRouter(prefix="/cases", tags=["documents"])


def _service(request: Request) -> DocumentService:
    service: DocumentService | None = getattr(request.app.state, "document_service", None)
    if service is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Document uploads are not set up on this server. Nothing was saved.",
        )
    return service


def _audit(
    request: Request,
    principal: Principal,
    action: Action,
    outcome: Outcome,
    case_id: uuid.UUID,
    details: dict[str, str],
) -> None:
    record_event(
        request,
        action,
        outcome,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        details=details,
    )


def _out(record: DocumentRecord) -> DocumentOut:
    return DocumentOut(**record.model_dump(exclude={"tenant_id", "storage_key"}))


@router.post(
    "/{case_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED
)
def upload_document(
    request: Request,
    case_id: uuid.UUID,
    file: UploadFile = File(...),  # noqa: B008
    category: DocumentCategory = Form(...),  # noqa: B008
    principal: Principal = Depends(require_permission(Permission.CASE_WRITE)),  # noqa: B008
) -> DocumentOut:
    """Upload a financial statement, credit report or supporting file. The file is checked by its
    contents, virus-scanned and only then stored under a random name in private storage."""
    service = _service(request)
    load_case_for(request, principal, case_id)
    try:
        record = service.upload(
            case_id=case_id,
            tenant_id=principal.tenant_id,
            uploaded_by=principal.subject,
            category=category,
            raw_filename=file.filename,
            stream=file.file,
        )
    except RejectedFileError as exc:
        _audit(
            request,
            principal,
            Action.DOCUMENT_REJECTED,
            Outcome.DENIED,
            case_id,
            {"reason": exc.code},
        )
        raise HTTPException(exc.status, exc.message) from None
    except UploadUnavailableError as exc:
        _audit(
            request,
            principal,
            Action.DOCUMENT_REJECTED,
            Outcome.FAILURE,
            case_id,
            {"reason": f"{exc}_unavailable"},
        )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The upload could not be completed right now. Nothing was saved. Try again shortly.",
        ) from None
    _audit(
        request,
        principal,
        Action.DOCUMENT_UPLOADED,
        Outcome.SUCCESS,
        case_id,
        {"document_id": str(record.id), "category": record.category.value},
    )
    return _out(record)


@router.get("/{case_id}/documents", response_model=list[DocumentOut])
def list_documents(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[DocumentOut]:
    load_case_for(request, principal, case_id)
    records = _service(request).store.list_for_case(case_id, principal.tenant_id)
    return [_out(r) for r in records]


@router.get("/{case_id}/documents/{document_id}/content")
def download_document(
    request: Request,
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> StreamingResponse:
    """Download as an attachment. The browser is told never to display or sniff the content."""
    service = _service(request)
    load_case_for(request, principal, case_id)
    record = service.store.get(document_id)
    if record is None or record.case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    assert_same_tenant(
        request,
        principal,
        record.tenant_id,
        resource_type="document",
        resource_id=str(document_id),
    )
    _audit(
        request,
        principal,
        Action.DOCUMENT_DOWNLOADED,
        Outcome.SUCCESS,
        case_id,
        {"document_id": str(document_id)},
    )
    chunks = service.open(record)
    try:
        first = next(chunks, b"")  # fail with a clean 503 before any header is sent
    except UploadUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The document could not be read right now. Try again shortly.",
        ) from None
    return StreamingResponse(
        chain([first], chunks),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(record.filename)}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Length": str(record.size_bytes),
        },
    )
