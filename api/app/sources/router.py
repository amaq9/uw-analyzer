"""Source and connector registry endpoints (FR-2.1, FR-2.2). The administrator maintains the
registry (`admin:manage`); roles that plan or read research may read it. Entries are per tenant.
No credentials are accepted or returned. The registry states capability, never that a source was
accessed (FR-2.7)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import assert_same_tenant, require_any_permission, require_permission
from app.auth.models import Permission, Principal
from app.sources.schemas import (
    AccessCategory,
    SourceCreate,
    SourceFields,
    SourceOut,
    SourceRecord,
    SourceUpdate,
    to_out,
)
from app.sources.store import DuplicateSourceKeyError, PostgresSourceStore

router = APIRouter(prefix="/sources", tags=["sources"])

_READERS = (Permission.ADMIN_MANAGE, Permission.CASE_READ, Permission.RESEARCH_RUN)


def _store(request: Request) -> PostgresSourceStore:
    store: PostgresSourceStore = request.app.state.source_store
    return store


def _load(request: Request, principal: Principal, source_id: uuid.UUID) -> SourceRecord:
    record = _store(request).get(source_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    assert_same_tenant(
        request, principal, record.tenant_id, resource_type="source", resource_id=str(source_id)
    )
    return record


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(
    request: Request,
    body: SourceCreate,
    principal: Principal = Depends(require_permission(Permission.ADMIN_MANAGE)),  # noqa: B008
) -> SourceOut:
    """Register a source. Health starts as UNKNOWN until something checks it."""
    try:
        record = _store(request).create(principal.tenant_id, principal.subject, body.model_dump())
    except DuplicateSourceKeyError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A source with this key already exists. Nothing was saved."
        ) from None
    record_event(
        request,
        Action.SOURCE_CREATED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="source",
        resource_id=str(record.id),
        details={"key": record.key, "access_category": record.access_category.value},
    )
    return to_out(record)


@router.get("", response_model=list[SourceOut])
def list_sources(
    request: Request,
    jurisdiction: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    access_category: AccessCategory | None = None,
    principal: Principal = Depends(require_any_permission(*_READERS)),  # noqa: B008
) -> list[SourceOut]:
    """The tenant's registry. `jurisdiction` also returns GLOBAL sources."""
    records = _store(request).list_for_tenant(
        principal.tenant_id,
        jurisdiction=jurisdiction.upper() if jurisdiction else None,
        access_category=access_category,
    )
    return [to_out(r) for r in records]


@router.get("/{source_id}", response_model=SourceOut)
def get_source(
    request: Request,
    source_id: uuid.UUID,
    principal: Principal = Depends(require_any_permission(*_READERS)),  # noqa: B008
) -> SourceOut:
    return to_out(_load(request, principal, source_id))


@router.patch("/{source_id}", response_model=SourceOut)
def update_source(
    request: Request,
    source_id: uuid.UUID,
    body: SourceUpdate,
    principal: Principal = Depends(require_permission(Permission.ADMIN_MANAGE)),  # noqa: B008
) -> SourceOut:
    """Change some fields (also how health is recorded for now). Send `expected_version`; a stale
    one returns 409 and saves nothing. The key never changes."""
    record = _load(request, principal, source_id)
    changes: dict[str, Any] = body.model_dump(
        mode="json", exclude={"expected_version"}, exclude_unset=True
    )
    if not changes:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Send at least one field to change."
        )
    field_changes = {k: v for k, v in changes.items() if k != "health"}
    if field_changes:
        merged = {**record.model_dump(include=set(SourceFields.model_fields)), **field_changes}
        try:
            checked = SourceFields(**merged)  # re-apply every rule to the result
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from None
        cleaned = checked.model_dump(mode="json")
        changes.update({k: cleaned[k] for k in field_changes})  # store the normalised values

    updated = _store(request).update(source_id, principal.tenant_id, body.expected_version, changes)
    if updated is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This source was changed by someone else. Reload it and try again. Nothing was saved.",
        )
    details = {"changed_fields": ",".join(sorted(changes)), "new_version": str(updated.version)}
    if "access_category" in changes:
        details["access_category"] = updated.access_category.value
    record_event(
        request,
        Action.SOURCE_UPDATED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="source",
        resource_id=str(source_id),
        details=details,
    )
    return to_out(updated)
