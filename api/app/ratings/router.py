"""Published agency opinions on a case. Recording one needs `draft:import` (the analyst role: an
underwriter, a reviewer or a Claude Code session); reading needs `case:read`. Each record keeps its
source, so nothing here is a claim without evidence. Records are append-only."""

import uuid

from fastapi import APIRouter, Depends, Request, status

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.ratings.schemas import PublishedRatingIn, PublishedRatingOut, to_out
from app.ratings.store import PostgresRatingStore

router = APIRouter(prefix="/cases", tags=["published-ratings"])


def _store(request: Request) -> PostgresRatingStore:
    store: PostgresRatingStore = request.app.state.rating_store
    return store


@router.post(
    "/{case_id}/published-ratings",
    response_model=PublishedRatingOut,
    status_code=status.HTTP_201_CREATED,
)
def record_published_rating(
    request: Request,
    case_id: uuid.UUID,
    body: PublishedRatingIn,
    principal: Principal = Depends(require_permission(Permission.DRAFT_IMPORT)),  # noqa: B008
) -> PublishedRatingOut:
    """Record an agency's published opinion with where it was read, when, and the quoted words."""
    load_case_for(request, principal, case_id)
    record = _store(request).add(
        tenant_id=principal.tenant_id, case_id=case_id, body=body, recorded_by=principal.subject
    )
    record_event(
        request,
        Action.PUBLISHED_RATING_RECORDED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        # Which agency only. The grade and reasons are Restricted case content.
        details={"agency": body.agency},
    )
    return to_out(record)


@router.get("/{case_id}/published-ratings", response_model=list[PublishedRatingOut])
def list_published_ratings(
    request: Request,
    case_id: uuid.UUID,
    latest: bool = True,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[PublishedRatingOut]:
    """The latest opinion of each agency, or every record newest first (`latest=false`)."""
    load_case_for(request, principal, case_id)
    store = _store(request)
    records = (
        store.latest_per_agency(case_id, principal.tenant_id)
        if latest
        else store.list_for_case(case_id, principal.tenant_id)
    )
    return [to_out(r) for r in records]
