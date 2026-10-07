"""Draft recommendation endpoints (ADR 0005, ADR 0008). The author supplies findings and the AI's
proposed amount; the server applies the approved policy and derives the outcome and final amount.
Every output is labelled as a draft for the underwriter and as a test product."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.audit.events import Action
from app.audit.events import Outcome as AuditOutcome
from app.audit.recorder import record_event
from app.auth.deps import assert_same_tenant, require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.cases.schemas import CaseStatus
from app.documents.store import PostgresDocumentStore
from app.recommendation.policy import Band, DeclineRule, PolicyInputError, derive
from app.recommendation.schemas import DraftImport, DraftOut, DraftRecord, EvidenceRef, to_out
from app.recommendation.store import PostgresDraftStore

router = APIRouter(prefix="/cases", tags=["draft-recommendations"])


def _drafts(request: Request) -> PostgresDraftStore:
    store: PostgresDraftStore = request.app.state.draft_store
    return store


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


def _check_documents(
    request: Request, principal: Principal, case_id: uuid.UUID, body: DraftImport
) -> None:
    """Every cited document must be a real upload of this case (P-02: no invented evidence)."""
    refs: list[EvidenceRef] = [e for r in body.reasons for e in r.evidence]
    refs += [e for f in body.decline_findings for e in f.evidence]
    cited = {e.document_id for e in refs if e.kind == "document"}
    if not cited:
        return
    store: PostgresDocumentStore = request.app.state.document_store
    known = {d.id for d in store.list_for_case(case_id, principal.tenant_id)}
    unknown = cited - known
    if unknown:
        raise _unprocessable(
            "A cited document is not part of this case: "
            + ", ".join(sorted(str(u) for u in unknown))
        )


@router.post(
    "/{case_id}/draft-recommendations",
    response_model=DraftOut,
    status_code=status.HTTP_201_CREATED,
)
def import_draft(
    request: Request,
    case_id: uuid.UUID,
    body: DraftImport,
    principal: Principal = Depends(require_permission(Permission.DRAFT_IMPORT)),  # noqa: B008
) -> DraftOut:
    """Record a draft recommendation written by an analyst session (assisted mode). The server
    derives the outcome and amount from the approved policy; the author cannot choose them."""
    case = load_case_for(request, principal, case_id)
    if case.status not in (CaseStatus.ENTITY_RESOLVED, CaseStatus.ENTITY_UNCONFIRMED):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The legal entity must be resolved, or recorded as not confirmed, before a "
            "recommendation can be drafted.",
        )
    unverified = [f.code for f in body.decline_findings if not f.verified]
    if unverified:
        raise _unprocessable(
            "A material adverse finding is not verified (" + ", ".join(unverified) + "). A person "
            "must resolve it before a draft can be made."
        )
    _check_documents(request, principal, case_id, body)

    verified = tuple(DeclineRule(f.code) for f in body.decline_findings)
    try:
        derived = derive(
            case_status=case.status,
            requested=case.exposure_amount,
            ai_proposed=body.ai_proposed_amount,
            financial_findings_weak=body.financial_findings_weak,
            verified_findings=verified,
        )
    except PolicyInputError as exc:
        raise _unprocessable(str(exc)) from None
    if derived.band is Band.REDUCED and not body.factors:
        raise _unprocessable(
            "Explain what lowered the amount: give at least one factor with its explanation."
        )

    content = {
        "summary": body.summary,
        "reasons": [r.model_dump(mode="json") for r in body.reasons],
        "decline_findings": [f.model_dump(mode="json") for f in body.decline_findings],
        "factors": [f.model_dump(mode="json") for f in body.factors],
        "information_gaps": body.information_gaps,
    }
    record = _drafts(request).add(
        case_id=case_id,
        tenant_id=principal.tenant_id,
        outcome=derived.outcome,
        band=derived.band,
        requested_amount=case.exposure_amount,
        requested_currency=case.exposure_currency,
        recommended_amount=derived.recommended_amount,
        ai_proposed_amount=body.ai_proposed_amount,
        rule_codes=[r.value for r in derived.rules],
        content=content,
        source=body.source.model_dump(mode="json"),
        policy_version=body.source.policy_version,
        created_by=principal.subject,
    )
    record_event(
        request,
        Action.DRAFT_IMPORTED,
        AuditOutcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        # Ids and codes only. Outcomes, amounts and reasons are Restricted case content.
        details={
            "draft_id": str(record.id),
            "version": str(record.version),
            "source": body.source.kind,
        },
    )
    return to_out(record)


@router.get("/{case_id}/draft-recommendations", response_model=list[DraftOut])
def list_drafts(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[DraftOut]:
    """The case's drafts, newest first. Older drafts are kept; nothing is overwritten."""
    load_case_for(request, principal, case_id)
    return [to_out(d) for d in _drafts(request).list_for_case(case_id, principal.tenant_id)]


def load_draft_for(
    request: Request, principal: Principal, case_id: uuid.UUID, draft_id: uuid.UUID
) -> DraftRecord:
    load_case_for(request, principal, case_id)
    record = _drafts(request).get(draft_id)
    if record is None or record.case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found.")
    assert_same_tenant(
        request, principal, record.tenant_id, resource_type="draft", resource_id=str(draft_id)
    )
    return record


@router.get("/{case_id}/draft-recommendations/{draft_id}", response_model=DraftOut)
def get_draft(
    request: Request,
    case_id: uuid.UUID,
    draft_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> DraftOut:
    return to_out(load_draft_for(request, principal, case_id, draft_id))
