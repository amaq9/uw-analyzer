"""Escalation endpoints (P-07). Reading needs `case:read`; raising needs `research:run`; resolving
needs `conflict:resolve` (reviewer). Resolution is an explicit, written, named human act and is
append-only. Nothing in the system resolves an escalation on its own."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.escalations.schemas import (
    EscalationCreate,
    EscalationList,
    EscalationOut,
    Kind,
    Resolution,
    ResolutionOutcome,
    ResolveIn,
)
from app.escalations.store import AlreadyResolvedError, PostgresEscalationStore
from app.evidence.router import conflict_comparison
from app.evidence.rules import Relation
from app.evidence.store import PostgresEvidenceStore

router = APIRouter(prefix="/cases", tags=["escalations"])


def _store(request: Request) -> PostgresEscalationStore:
    store: PostgresEscalationStore = request.app.state.escalation_store
    return store


def _out(request: Request, row: dict[str, Any]) -> EscalationOut:
    res = _store(request).resolution_of(row["id"])
    comparison = (
        conflict_comparison(request, row["claim_id"])
        if row["kind"] == Kind.CONFLICT.value and row["claim_id"]
        else []
    )
    return EscalationOut(
        **{k: row[k] for k in ("id", "case_id", "kind", "claim_id", "description")},
        state="RESOLVED" if res else "OPEN",
        raised_by_system=row["raised_by_system"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        resolution=Resolution(**{k: res[k] for k in Resolution.model_fields}) if res else None,
        comparison=comparison,
    )


def _load(
    request: Request, principal: Principal, case_id: uuid.UUID, escalation_id: uuid.UUID
) -> dict[str, Any]:
    load_case_for(request, principal, case_id)
    row = _store(request).get(escalation_id)
    if row is None or row["case_id"] != case_id or row["tenant_id"] != principal.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Escalation not found.")
    return row


def _audit(
    request: Request, principal: Principal, action: Action, case_id: uuid.UUID, ids: dict[str, str]
) -> None:
    record_event(
        request,
        action,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        details=ids,
    )


@router.get("/{case_id}/escalations", response_model=EscalationList)
def list_escalations(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> EscalationList:
    """All escalations of the case, with how many are still open."""
    load_case_for(request, principal, case_id)
    items = [_out(request, r) for r in _store(request).list_for_case(case_id, principal.tenant_id)]
    return EscalationList(open_count=sum(i.state == "OPEN" for i in items), items=items)


@router.get("/{case_id}/escalations/{escalation_id}", response_model=EscalationOut)
def get_escalation(
    request: Request,
    case_id: uuid.UUID,
    escalation_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> EscalationOut:
    return _out(request, _load(request, principal, case_id, escalation_id))


@router.post(
    "/{case_id}/escalations", response_model=EscalationOut, status_code=status.HTTP_201_CREATED
)
def raise_escalation(
    request: Request,
    case_id: uuid.UUID,
    body: EscalationCreate,
    principal: Principal = Depends(require_permission(Permission.RESEARCH_RUN)),  # noqa: B008
) -> EscalationOut:
    """A person flags something that needs review (for example a material ambiguity)."""
    load_case_for(request, principal, case_id)
    if body.claim_id is not None:
        evidence: PostgresEvidenceStore = request.app.state.evidence_store
        claim = evidence.get_claim(body.claim_id)
        if claim is None or claim.case_id != case_id or claim.tenant_id != principal.tenant_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "That claim is not part of this case."
            )
    row = _store(request).add(
        {
            "tenant_id": principal.tenant_id,
            "case_id": case_id,
            "kind": body.kind,
            "claim_id": body.claim_id,
            "description": body.description,
            "raised_by_system": False,
            "created_by": principal.subject,
        }
    )
    _audit(request, principal, Action.ESCALATION_RAISED, case_id, {"escalation_id": str(row["id"])})
    return _out(request, row)


@router.post("/{case_id}/escalations/{escalation_id}/resolution", response_model=EscalationOut)
def resolve_escalation(
    request: Request,
    case_id: uuid.UUID,
    escalation_id: uuid.UUID,
    body: ResolveIn,
    principal: Principal = Depends(require_permission(Permission.CONFLICT_RESOLVE)),  # noqa: B008
) -> EscalationOut:
    """A named reviewer resolves the escalation in writing. For a conflict they choose which side
    prevails and name the evidence preferred; a claim's verification then follows that choice."""
    row = _load(request, principal, case_id, escalation_id)
    unprocessable = status.HTTP_422_UNPROCESSABLE_CONTENT
    if row["kind"] == Kind.CONFLICT.value:
        if body.outcome is ResolutionOutcome.NO_CLAIM_CHANGE:
            raise HTTPException(unprocessable, "A conflict is resolved by preferring one side.")
        wanted = (
            Relation.SUPPORTS
            if body.outcome is ResolutionOutcome.SUPPORTING_PREVAILS
            else Relation.CONTRADICTS
        )
        evidence: PostgresEvidenceStore = request.app.state.evidence_store
        sides = {
            link.evidence_id
            for link in evidence.links_of(row["claim_id"])
            if link.relation is wanted
        }
        if body.preferred_evidence_id not in sides:
            raise HTTPException(
                unprocessable,
                "The preferred evidence must be linked to the claim on the side that prevails.",
            )
    elif body.outcome is not ResolutionOutcome.NO_CLAIM_CHANGE:
        raise HTTPException(unprocessable, "Only a conflict can change a claim's verification.")
    try:
        _store(request).resolve(
            {
                "escalation_id": escalation_id,
                "tenant_id": principal.tenant_id,
                "outcome": body.outcome.value,
                "preferred_evidence_id": body.preferred_evidence_id,
                "explanation": body.explanation,
                "resolved_by": principal.subject,
            }
        )
    except AlreadyResolvedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This escalation has already been resolved."
        ) from None
    _audit(
        request,
        principal,
        Action.ESCALATION_RESOLVED,
        case_id,
        {"escalation_id": str(escalation_id), "outcome": body.outcome.value},
    )
    return _out(request, _load(request, principal, case_id, escalation_id))
