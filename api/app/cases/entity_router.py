"""Entity resolution endpoints (FR-1.4 to FR-1.7). Resolving or reopening is always an explicit
human action by a signed-in user; no endpoint, job or default can do it for them (P-03, P-07)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.cases.entities import (
    CandidateCreate,
    CandidateOut,
    Readiness,
    ReopenRequest,
    ResolveRequest,
    UnconfirmedRequest,
    research_readiness,
)
from app.cases.entity_store import (
    CandidateMissingError,
    EntityConflictError,
    PostgresEntityStore,
)
from app.cases.schemas import CaseOut, to_out
from app.cases.store import PostgresCaseStore

router = APIRouter(prefix="/cases", tags=["entity-resolution"])


def _entities(request: Request) -> PostgresEntityStore:
    store: PostgresEntityStore = request.app.state.entity_store
    return store


def _audit(
    request: Request,
    principal: Principal,
    action: Action,
    case_id: uuid.UUID,
    details: dict[str, str] | None = None,
) -> None:
    # Ids and codes only. Entity names and free-text reasons are Restricted: never audit details.
    record_event(
        request,
        action,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        details=details,
    )


@router.get("/{case_id}/entity-candidates", response_model=list[CandidateOut])
def list_candidates(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[CandidateOut]:
    load_case_for(request, principal, case_id)
    return _entities(request).list_candidates(case_id, principal.tenant_id)


@router.post(
    "/{case_id}/entity-candidates", response_model=CandidateOut, status_code=status.HTTP_201_CREATED
)
def add_candidate(
    request: Request,
    case_id: uuid.UUID,
    body: CandidateCreate,
    principal: Principal = Depends(require_permission(Permission.CASE_WRITE)),  # noqa: B008
) -> CandidateOut:
    """Add a plausible legal entity. Two or more open candidates make the case ambiguous."""
    load_case_for(request, principal, case_id)
    try:
        candidate, new_status = _entities(request).add_candidate(
            case_id, principal.tenant_id, principal.subject, body.model_dump()
        )
    except EntityConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    _audit(
        request,
        principal,
        Action.ENTITY_CANDIDATE_ADDED,
        case_id,
        {"candidate_id": str(candidate.id), "case_status": new_status.value},
    )
    return candidate


@router.post("/{case_id}/entity-resolution", response_model=CaseOut)
def resolve_entity(
    request: Request,
    case_id: uuid.UUID,
    body: ResolveRequest,
    principal: Principal = Depends(require_permission(Permission.CASE_WRITE)),  # noqa: B008
) -> CaseOut:
    """A person chooses the one exact legal entity. This is the only way a case becomes resolved."""
    load_case_for(request, principal, case_id)
    try:
        _entities(request).resolve(
            case_id, principal.tenant_id, principal.subject, body.candidate_id, body.note
        )
    except EntityConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    except CandidateMissingError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "That candidate is not an open candidate for this case."
        ) from None
    _audit(
        request,
        principal,
        Action.ENTITY_RESOLVED,
        case_id,
        {"candidate_id": str(body.candidate_id)},
    )
    return _reload(request, case_id)


@router.post("/{case_id}/entity-resolution/reopen", response_model=CaseOut)
def reopen_entity(
    request: Request,
    case_id: uuid.UUID,
    body: ReopenRequest,
    principal: Principal = Depends(require_permission(Permission.CASE_WRITE)),  # noqa: B008
) -> CaseOut:
    """Override a resolved entity. A reason is mandatory; the reopening is audited and logged."""
    load_case_for(request, principal, case_id)
    try:
        new_status = _entities(request).reopen(
            case_id, principal.tenant_id, principal.subject, body.reason
        )
    except EntityConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    _audit(request, principal, Action.ENTITY_REOPENED, case_id, {"case_status": new_status.value})
    return _reload(request, case_id)


@router.post("/{case_id}/entity-resolution/unconfirmed", response_model=CaseOut)
def record_entity_unconfirmed(
    request: Request,
    case_id: uuid.UUID,
    body: UnconfirmedRequest,
    principal: Principal = Depends(require_permission(Permission.CASE_WRITE)),  # noqa: B008
) -> CaseOut:
    """A person records that the legal entity could not be confirmed or found. A reason is
    mandatory; it is kept in the append-only resolution log and the action is audited."""
    load_case_for(request, principal, case_id)
    try:
        _entities(request).mark_unconfirmed(
            case_id, principal.tenant_id, principal.subject, body.reason
        )
    except EntityConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    _audit(request, principal, Action.ENTITY_UNCONFIRMED, case_id)
    return _reload(request, case_id)


@router.get("/{case_id}/research-readiness", response_model=Readiness)
def get_research_readiness(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> Readiness:
    """Whether research may start, and the plain-language reason if not (AC-01)."""
    record = load_case_for(request, principal, case_id)
    open_count = _entities(request).open_candidate_count(case_id)
    return research_readiness(record.status, open_count)


def _reload(request: Request, case_id: uuid.UUID) -> CaseOut:
    cases: PostgresCaseStore = request.app.state.case_store
    record = cases.get(case_id)
    if record is None:  # pragma: no cover - cannot happen right after a successful action
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found.")
    return to_out(record)
