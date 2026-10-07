"""Case endpoints (FR-1.1, FR-1.3, FR-1.7). The server enforces permissions, tenant isolation and
every rule; the UI is never the only enforcement point."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import assert_same_tenant, require_permission
from app.auth.models import Permission, Principal
from app.cases.schemas import (
    CaseCreate,
    CaseFields,
    CaseOut,
    CaseRecord,
    CaseUpdate,
    to_out,
)
from app.cases.store import PostgresCaseStore

router = APIRouter(prefix="/cases", tags=["cases"])

_ChangeNothing = "Nothing to change: send at least one field."


def _store(request: Request) -> PostgresCaseStore:
    store: PostgresCaseStore = request.app.state.case_store
    return store


def _load_for(request: Request, principal: Principal, case_id: uuid.UUID) -> CaseRecord:
    """Find a case and enforce tenant isolation. Another tenant's case looks like a missing one."""
    record = _store(request).get(case_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found.")
    assert_same_tenant(
        request, principal, record.tenant_id, resource_type="case", resource_id=str(case_id)
    )
    return record


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
def create_case(
    request: Request,
    body: CaseCreate,
    principal: Principal = Depends(require_permission(Permission.CASE_WRITE)),  # noqa: B008
) -> CaseOut:
    """Create a case. Only a legal or trading name is required; the rest is tracked as gaps."""
    record = _store(request).create(
        principal.tenant_id, principal.subject, body.model_dump(exclude_none=True)
    )
    record_event(
        request,
        Action.CASE_CREATED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(record.id),
    )
    return to_out(record)


@router.get("", response_model=list[CaseOut])
def list_cases(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[CaseOut]:
    """The caller's own tenant's cases, newest first."""
    records = _store(request).list_for_tenant(principal.tenant_id, limit, offset)
    return [to_out(r) for r in records]


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> CaseOut:
    """One case. Viewing Restricted case content is itself audited."""
    record = _load_for(request, principal, case_id)
    record_event(
        request,
        Action.CASE_VIEWED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
    )
    return to_out(record)


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(
    request: Request,
    case_id: uuid.UUID,
    body: CaseUpdate,
    principal: Principal = Depends(require_permission(Permission.CASE_WRITE)),  # noqa: B008
) -> CaseOut:
    """Change some fields. Send `expected_version`; a stale one returns 409 and saves nothing."""
    record = _load_for(request, principal, case_id)
    changes: dict[str, Any] = body.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if not changes:
        raise HTTPException(422, _ChangeNothing)

    merged = {**record.model_dump(include=set(CaseFields.model_fields)), **changes}
    try:
        CaseCreate(**merged)  # re-apply every rule to the result, not just the changed fields
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None

    updated = _store(request).update(case_id, principal.tenant_id, body.expected_version, changes)
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This case was changed by someone else. Reload it and try again. Nothing was saved.",
        )
    record_event(
        request,
        Action.CASE_UPDATED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        # Field names only, never the values: case content is Restricted.
        details={"changed_fields": ",".join(sorted(changes)), "new_version": str(updated.version)},
    )
    return to_out(updated)
