"""Evidence, claim and verification endpoints (Phase 3). Writing needs `research:run`; reading needs
`case:read`. Everything is tenant-scoped and audited with ids only.

Rules enforced here, on the server:
- Connector evidence must point at a logged, successful connector call of this case: nothing else
  can show a source was accessed (P-01). Documents must be real uploads of this case.
- Verification status is never accepted from a caller. It is computed from the linked evidence
  by `app.evidence.rules` every time it is shown (P-05, FR-3.4).
- Evidence, claims and links are append-only; mistakes are corrected by adding, not editing.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.documents.store import PostgresDocumentStore
from app.escalations.store import PostgresEscalationStore
from app.evidence.rules import (
    RULES_VERSION,
    ClaimFacts,
    EvidenceFacts,
    Freshness,
    Relation,
    freshness,
    verify,
)
from app.evidence.schemas import (
    ClaimCreate,
    ClaimOut,
    ClaimRecord,
    EvidenceCreate,
    EvidenceOut,
    EvidenceRecord,
    LinkIn,
    LinkOut,
    LinkRecord,
    Verification,
    evidence_out,
)
from app.evidence.store import DuplicateLinkError, PostgresEvidenceStore
from app.research.run_store import PostgresRunQueue
from app.research.store import PostgresResearchStore
from app.sources.store import PostgresSourceStore

router = APIRouter(prefix="/cases", tags=["evidence"])

_UNAVAILABLE_STATES = ("NOT_AVAILABLE", "FAILED", "SKIPPED")


def _store(request: Request) -> PostgresEvidenceStore:
    store: PostgresEvidenceStore = request.app.state.evidence_store
    return store


def _bad(message: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)


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
        details=ids,  # ids only: excerpts and claim text are Restricted case content
    )


def _evidence_date(e: EvidenceRecord) -> date:
    return e.event_on or e.published_on or e.accessed_at.date()


def _fresh(e: EvidenceRecord) -> Freshness:
    return freshness(e.evidence_type, _evidence_date(e), datetime.now(UTC).date())


def _facts(e: EvidenceRecord) -> EvidenceFacts:
    return EvidenceFacts(e.source_class, e.discovery_only, e.is_primary, e.origin)


def _load_evidence(
    request: Request, principal: Principal, case_id: uuid.UUID, evidence_id: uuid.UUID
) -> EvidenceRecord:
    record = _store(request).get_evidence(evidence_id)
    if record is None or record.case_id != case_id or record.tenant_id != principal.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found.")
    return record


def _active_resolution(
    request: Request, claim_id: uuid.UUID, pairs: list[tuple[LinkRecord, EvidenceRecord]]
) -> str | None:
    """A person's resolution counts only if it came after the newest reliable contradicting link,
    so fresh contradicting evidence reopens the question."""
    escalations: PostgresEscalationStore = request.app.state.escalation_store
    resolution = escalations.latest_conflict_resolution(claim_id)
    if resolution is None or resolution["outcome"] == "NO_CLAIM_CHANGE":
        return None
    newest = max(
        (
            link.created_at
            for link, e in pairs
            if link.relation is Relation.CONTRADICTS and _facts(e).reliable
        ),
        default=None,
    )
    if newest is not None and resolution["resolved_at"] < newest:
        return None
    return str(resolution["outcome"])


def conflict_comparison(request: Request, claim_id: uuid.UUID) -> list[dict[str, Any]]:
    """Each linked source side by side on authority, date, specificity, independence and quality."""
    store = _store(request)
    rows: list[dict[str, Any]] = []
    for link in store.links_of(claim_id):
        e = store.get_evidence(link.evidence_id)
        if e is None:
            continue
        rows.append(
            {
                "side": link.relation.value,
                "evidence_id": str(e.id),
                "title": e.title,
                "origin": e.origin,
                "authority": e.source_class,
                "date": _evidence_date(e).isoformat(),
                "freshness": _fresh(e).value,
                "specificity": "primary record" if e.is_primary else "secondary report",
                "data_quality": ("discovery only; " if e.discovery_only else "")
                + (
                    "class declared by author"
                    if e.class_basis == "author_declared"
                    else "class from registry"
                ),
            }
        )
    origins = {
        side: {r["origin"] for r in rows if r["side"] == side}
        for side in ("SUPPORTS", "CONTRADICTS")
    }
    independent = not (origins["SUPPORTS"] & origins["CONTRADICTS"])
    for r in rows:
        r["independent_of_other_side"] = independent
    return rows


def _raise_conflict_if_needed(
    request: Request, principal: Principal, claim: ClaimRecord, out: ClaimOut
) -> None:
    """A material claim with an unresolved reliable contradiction needs a person (P-07)."""
    if not (claim.material and out.verification.conflict):
        return
    escalations: PostgresEscalationStore = request.app.state.escalation_store
    row = escalations.add_conflict_if_none_open(
        {
            "tenant_id": principal.tenant_id,
            "case_id": claim.case_id,
            "kind": "CONFLICT",
            "claim_id": claim.id,
            "description": "Reliable sources disagree about a material claim. A person must "
            "decide which evidence prevails.",
            "raised_by_system": True,
            "created_by": "system",
        }
    )
    if row is not None:
        _audit(
            request,
            principal,
            Action.ESCALATION_RAISED,
            claim.case_id,
            {"escalation_id": str(row["id"])},
        )


def _claim_out(request: Request, claim: ClaimRecord) -> ClaimOut:
    store = _store(request)
    links = store.links_of(claim.id)
    pairs = []
    for link in links:
        ev = store.get_evidence(link.evidence_id)
        if ev is not None:
            pairs.append((link, ev))
    supporting = tuple(_facts(e) for link, e in pairs if link.relation is Relation.SUPPORTS)
    contradicting = tuple(_facts(e) for link, e in pairs if link.relation is Relation.CONTRADICTS)
    verdict = verify(
        ClaimFacts(
            classification=claim.classification,
            material=claim.material,
            adverse=claim.adverse,
            source_unavailable=claim.unavailable_step_id is not None,
            supporting=supporting,
            contradicting=contradicting,
            conflict_resolution=_active_resolution(request, claim.id, pairs),
        )
    )
    reliable_fresh = [
        _fresh(e) for link, e in pairs if link.relation is Relation.SUPPORTS and _facts(e).reliable
    ]
    order = [Freshness.CURRENT, Freshness.RECENT, Freshness.STALE, Freshness.HISTORICAL]
    best = min(reliable_fresh, key=order.index) if reliable_fresh else None
    return ClaimOut(
        id=claim.id,
        case_id=claim.case_id,
        text=claim.text,
        classification=claim.classification,
        material=claim.material,
        adverse=claim.adverse,
        credit_relevance=claim.credit_relevance,
        category=claim.category,
        unavailable_step_id=claim.unavailable_step_id,
        basis_claim_ids=store.basis_of(claim.id),
        verification=Verification(
            status=verdict.status,
            reasons=verdict.reasons,
            needs=verdict.needs,
            conflict=verdict.conflict,
            rules_version=RULES_VERSION,
        ),
        freshness=best,
        links=[
            LinkOut(
                id=link.id,
                relation=link.relation,
                notes=link.notes,
                evidence=evidence_out(e, _fresh(e)),
            )
            for link, e in pairs
        ],
        created_by=claim.created_by,
        created_at=claim.created_at,
    )


# --- evidence ---------------------------------------------------------------------------------


@router.post("/{case_id}/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
def add_evidence(
    request: Request,
    case_id: uuid.UUID,
    body: EvidenceCreate,
    principal: Principal = Depends(require_permission(Permission.RESEARCH_RUN)),  # noqa: B008
) -> EvidenceOut:
    """Record a piece of evidence. Connector evidence must come from a logged successful call."""
    load_case_for(request, principal, case_id)
    now = datetime.now(UTC)
    for label, day in (("published", body.published_on), ("event", body.event_on)):
        if day is not None and day > now.date():
            raise _bad(f"The {label} date cannot be in the future.")

    values: dict[str, object] = {
        "tenant_id": principal.tenant_id,
        "case_id": case_id,
        "kind": body.kind,
        "evidence_type": body.evidence_type.value,
        "title": body.title,
        "origin": body.origin,
        "published_on": body.published_on,
        "event_on": body.event_on,
        "excerpt": body.excerpt,
        "is_primary": body.is_primary,
        "content_hash": body.content_hash,
        "created_by": principal.subject,
        "url": body.url,
        "source_id": None,
        "connector_call_id": None,
        "document_id": None,
    }
    if body.kind == "CONNECTOR":
        queue: PostgresRunQueue = request.app.state.run_queue
        assert body.connector_call_id is not None  # noqa: S101 - validated by the schema
        call = queue.get_call(body.connector_call_id)
        if call is None or call.case_id != case_id or call.tenant_id != principal.tenant_id:
            raise _bad("That connector call is not part of this case.")
        if call.outcome != "SUCCESS" or not call.provenance_ref:
            raise _bad("Only a successful connector call that returned material can be evidence.")
        sources: PostgresSourceStore = request.app.state.source_store
        source = sources.get(call.source_id)
        if source is None:  # pragma: no cover - calls reference real sources
            raise _bad("The source of that call is not in the registry.")
        values.update(
            source_class=source.source_class.value,
            class_basis="registry",
            source_id=call.source_id,
            connector_call_id=call.id,
            accessed_at=call.ended_at,
            provenance_ref=call.provenance_ref,
            discovery_only=call.access_status == "DISCOVERY_ONLY",
        )
    elif body.kind == "DOCUMENT":
        docs: PostgresDocumentStore = request.app.state.document_store
        known = {d.id: d for d in docs.list_for_case(case_id, principal.tenant_id)}
        doc = known.get(body.document_id) if body.document_id else None
        if doc is None:
            raise _bad("That document is not part of this case.")
        values.update(
            source_class=body.source_class,
            class_basis="author_declared",
            document_id=doc.id,
            accessed_at=now,
            provenance_ref=f"document:{doc.id}",
            content_hash=body.content_hash or doc.sha256,
            discovery_only=False,
        )
    else:
        assert body.retrieved_at is not None  # noqa: S101 - validated by the schema
        if body.retrieved_at > now + timedelta(minutes=5):
            raise _bad("The time the source was read cannot be in the future.")
        values.update(
            source_class=body.source_class,
            class_basis="author_declared",
            accessed_at=body.retrieved_at,
            provenance_ref=None,
            discovery_only=False,
        )
    record = _store(request).add_evidence(values)
    _audit(request, principal, Action.EVIDENCE_ADDED, case_id, {"evidence_id": str(record.id)})
    return evidence_out(record, _fresh(record))


@router.get("/{case_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[EvidenceOut]:
    load_case_for(request, principal, case_id)
    return [
        evidence_out(e, _fresh(e))
        for e in _store(request).list_evidence(case_id, principal.tenant_id)
    ]


@router.get("/{case_id}/evidence/{evidence_id}", response_model=EvidenceOut)
def get_evidence(
    request: Request,
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> EvidenceOut:
    load_case_for(request, principal, case_id)
    record = _load_evidence(request, principal, case_id, evidence_id)
    return evidence_out(record, _fresh(record))


# --- claims -----------------------------------------------------------------------------------


def _check_links(
    request: Request, principal: Principal, case_id: uuid.UUID, links: list[LinkIn]
) -> None:
    for link in links:
        record = _store(request).get_evidence(link.evidence_id)
        if record is None or record.case_id != case_id or record.tenant_id != principal.tenant_id:
            raise _bad("A linked evidence item is not part of this case.")


@router.post("/{case_id}/claims", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def add_claim(
    request: Request,
    case_id: uuid.UUID,
    body: ClaimCreate,
    principal: Principal = Depends(require_permission(Permission.RESEARCH_RUN)),  # noqa: B008
) -> ClaimOut:
    """Record a claim with its evidence links. The response shows the verification status the
    server computed; there is no way to send one."""
    load_case_for(request, principal, case_id)
    _check_links(request, principal, case_id, body.evidence)
    store = _store(request)
    for basis_id in body.basis_claim_ids:
        basis = store.get_claim(basis_id)
        if basis is None or basis.case_id != case_id or basis.tenant_id != principal.tenant_id:
            raise _bad("A claim it is based on is not part of this case.")
    if body.unavailable_step_id is not None:
        research: PostgresResearchStore = request.app.state.research_store
        step = research.get_step(body.unavailable_step_id)
        if (
            step is None
            or research.case_of_step(step.id) != case_id
            or step.state.value not in _UNAVAILABLE_STATES
        ):
            raise _bad("That research step is not an unavailable or failed step of this case.")
    claim = store.add_claim(
        {
            "tenant_id": principal.tenant_id,
            "case_id": case_id,
            "text": body.text,
            "classification": body.classification.value,
            "material": body.material,
            "adverse": body.adverse,
            "credit_relevance": body.credit_relevance,
            "category": body.category,
            "unavailable_step_id": body.unavailable_step_id,
            "created_by": principal.subject,
        },
        body.basis_claim_ids,
        [(link.evidence_id, link.relation, link.notes) for link in body.evidence],
    )
    _audit(request, principal, Action.CLAIM_ADDED, case_id, {"claim_id": str(claim.id)})
    out = _claim_out(request, claim)
    _raise_conflict_if_needed(request, principal, claim, out)
    return out


def _load_claim(
    request: Request, principal: Principal, case_id: uuid.UUID, claim_id: uuid.UUID
) -> ClaimRecord:
    load_case_for(request, principal, case_id)
    claim = _store(request).get_claim(claim_id)
    if claim is None or claim.case_id != case_id or claim.tenant_id != principal.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Claim not found.")
    return claim


@router.post(
    "/{case_id}/claims/{claim_id}/evidence-links",
    response_model=ClaimOut,
    status_code=status.HTTP_201_CREATED,
)
def link_evidence(
    request: Request,
    case_id: uuid.UUID,
    claim_id: uuid.UUID,
    body: LinkIn,
    principal: Principal = Depends(require_permission(Permission.RESEARCH_RUN)),  # noqa: B008
) -> ClaimOut:
    """Add evidence to an existing claim. Links are never edited or removed."""
    claim = _load_claim(request, principal, case_id, claim_id)
    _check_links(request, principal, case_id, [body])
    try:
        _store(request).add_link(
            claim_id, body.evidence_id, body.relation, body.notes, principal.subject
        )
    except DuplicateLinkError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That evidence is already linked to this claim."
        ) from None
    _audit(
        request,
        principal,
        Action.CLAIM_LINKED,
        case_id,
        {
            "claim_id": str(claim_id),
            "evidence_id": str(body.evidence_id),
            "relation": body.relation.value,
        },
    )
    out = _claim_out(request, claim)
    _raise_conflict_if_needed(request, principal, claim, out)
    return out


@router.get("/{case_id}/claims", response_model=list[ClaimOut])
def list_claims(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[ClaimOut]:
    load_case_for(request, principal, case_id)
    return [
        _claim_out(request, c) for c in _store(request).list_claims(case_id, principal.tenant_id)
    ]


@router.get("/{case_id}/claims/{claim_id}", response_model=ClaimOut)
def get_claim(
    request: Request,
    case_id: uuid.UUID,
    claim_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> ClaimOut:
    return _claim_out(request, _load_claim(request, principal, case_id, claim_id))
