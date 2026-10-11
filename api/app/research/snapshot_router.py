"""Read a stored snapshot (the exact bytes a connector received). Needs `case:read`, is tenant- and
case-scoped, checks the SHA-256 in the reference against the stored bytes, and is audited. This is
how a person, or an analyst session, shows the source behind a claim (P-01, P-02)."""

import hashlib
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.documents.service import DocumentService
from app.documents.storage import StorageUnavailableError
from app.research.snapshots import SnapshotStore

router = APIRouter(prefix="/cases", tags=["research"])
_REF = re.compile(
    r"^snapshot://(snapshots/[A-Za-z0-9._-]+/[0-9a-f-]{36}/[0-9a-f]{32})#sha256=([0-9a-f]{64})$"
)


@router.get("/{case_id}/snapshots")
def read_snapshot(
    request: Request,
    case_id: uuid.UUID,
    ref: str = Query(max_length=300, description="A provenance reference from a connector call"),
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> Response:
    """The stored source material for a provenance reference of this case."""
    load_case_for(request, principal, case_id)
    match = _REF.fullmatch(ref)
    if match is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Not a snapshot reference.")
    key, digest = match.groups()
    # The reference must belong to this tenant and case: no reading another case's material.
    if not key.startswith(f"snapshots/{principal.tenant_id}/{case_id}/"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found.")
    service: DocumentService | None = getattr(request.app.state, "document_service", None)
    if service is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Storage is not set up.")
    try:
        body = SnapshotStore(service.storage).read(key)
    except StorageUnavailableError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snapshot not found.") from None
    if hashlib.sha256(body).hexdigest() != digest:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The stored snapshot does not match its recorded hash."
        )
    record_event(
        request,
        Action.SNAPSHOT_READ,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        details={"sha256": digest},
    )
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": "attachment", "X-Content-Type-Options": "nosniff"},
    )
