"""Builds the report content and checks the completion gates from the case's own records. Pure
reading: it never writes, never searches and never invents. Wording is fixed templates."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request

from app.cases.entities import research_readiness
from app.cases.entity_store import PostgresEntityStore
from app.cases.schemas import CaseRecord, information_gaps
from app.escalations.store import PostgresEscalationStore
from app.evidence.schemas import ClaimOut
from app.reports.schemas import (
    ClaimRow,
    Confidence,
    ConfidenceLevel,
    Counts,
    EscalationRow,
    FinancialsRow,
    Gate,
    ReportContent,
    SourceRow,
)
from app.research.run_store import PostgresRunQueue
from app.research.store import PostgresResearchStore

PAYMENT_LIMITATION = "Payment behaviour was not assessed (data not used in this product)."
RELIABLE_FRESH = ("CURRENT", "RECENT")


def _claim_row(c: ClaimOut) -> ClaimRow:
    return ClaimRow(
        claim_id=c.id,
        text=c.text,
        classification=c.classification.value,
        material=c.material,
        adverse=c.adverse,
        verification_status=c.verification.status.value,
        freshness=c.freshness.value if c.freshness else None,
        conflict=c.verification.conflict,
        evidence_ids=[link.evidence.id for link in c.links],
    )


def _confidence(
    material: list[ClaimOut], open_escalations: int, accessed_anything: bool
) -> Confidence:
    facts = [c for c in material if c.classification.value in ("FACT", "UNVERIFIED")]
    why: list[str] = []
    if not accessed_anything:
        why.append("No source was accessed or recorded.")
    if not facts:
        why.append("No material factual claim has been assessed.")
    if open_escalations:
        why.append(f"{open_escalations} item(s) still need human review.")
    weak_adverse = [c for c in facts if c.adverse and c.verification.status.value != "VERIFIED"]
    if weak_adverse:
        why.append(f"{len(weak_adverse)} material adverse claim(s) are not verified.")
    if why:
        return Confidence(level=ConfidenceLevel.LOW, explanations=why)

    unverified = [c for c in facts if c.verification.status.value != "VERIFIED"]
    aged = [c for c in facts if c.freshness is None or c.freshness.value not in RELIABLE_FRESH]
    if unverified:
        why.append(f"{len(unverified)} of {len(facts)} material claim(s) are not fully verified.")
    if aged:
        why.append(f"{len(aged)} material claim(s) rest on older evidence.")
    if why:
        return Confidence(level=ConfidenceLevel.MODERATE, explanations=why)
    return Confidence(
        level=ConfidenceLevel.HIGH,
        explanations=[
            f"All {len(facts)} material claim(s) are verified by reliable, recent evidence.",
            "No item is waiting for human review.",
        ],
    )


def build(
    request: Request, case: CaseRecord, claims: list[ClaimOut], now: datetime | None = None
) -> tuple[ReportContent, list[Gate], dict[str, Any]]:
    """Returns the content, the gate results and the versions used."""
    now = now or datetime.now(UTC)
    research: PostgresResearchStore = request.app.state.research_store
    queue: PostgresRunQueue = request.app.state.run_queue
    escalation_store: PostgresEscalationStore = request.app.state.escalation_store
    entities: PostgresEntityStore = request.app.state.entity_store
    case_id: uuid.UUID = case.id

    runs = research.list_runs(case_id, case.tenant_id)  # newest first
    finished = [r for r in runs if r.status.value in ("COMPLETED", "FAILED")]
    in_flight = [r for r in runs if r.status.value in ("QUEUED", "RUNNING")]
    latest = finished[0] if finished else None

    log: list[SourceRow] = []
    accessed_steps: set[uuid.UUID] = set()
    connectors: dict[str, str] = {}
    sources_accessed: set[str] = set()
    for run in runs:
        calls = queue.calls_for_run(run.id)
        accessed_steps |= {c.step_id for c in calls if c.outcome == "SUCCESS"}
        sources_accessed |= {c.source_key for c in calls if c.outcome == "SUCCESS"}
        connectors.update(run.versions.get("connectors") or {})
    if latest is not None:
        for step in research.steps_for_run(latest.id):
            snap = step.source_snapshot
            log.append(
                SourceRow(
                    category=step.category.value,
                    source_key=str(snap["key"]) if "key" in snap else None,
                    source_name=str(snap["name"]) if "name" in snap else None,
                    state=step.state.value,
                    accessed=step.id in accessed_steps,
                    reason=step.reason,
                    attempts=step.attempts,
                )
            )
    unavailable = [r for r in log if r.state in ("NOT_AVAILABLE", "SKIPPED", "FAILED")]

    # Evidence-based counts (documents and web material recorded by people or sessions).
    evidence_store = request.app.state.evidence_store
    evidence = evidence_store.list_evidence(case_id, case.tenant_id)
    financials = [
        FinancialsRow(
            evidence_id=e.id,
            title=e.title,
            origin=e.origin,
            period_end=e.event_on,
            published_on=e.published_on,
            accessed_at=e.accessed_at,
            kind=e.kind,
            source_class=e.source_class,
            source_class_basis=e.class_basis,
        )
        for e in sorted(evidence, key=lambda x: x.created_at)
        if e.evidence_type == "FINANCIAL"
    ]
    documents = {e.document_id for e in evidence if e.kind == "DOCUMENT"}
    web = {e.origin for e in evidence if e.kind == "WEB"}

    material = [c for c in claims if c.material]
    verified_material = [c for c in material if c.verification.status.value == "VERIFIED"]
    unverified = [
        c
        for c in claims
        if c.classification.value in ("FACT", "UNVERIFIED")
        and c.verification.status.value != "VERIFIED"
    ]
    gaps = [g.description for g in information_gaps(case)]

    escalations = escalation_store.list_for_case(case_id, case.tenant_id)
    esc_rows: list[EscalationRow] = []
    for e in escalations:
        res = escalation_store.resolution_of(e["id"])
        esc_rows.append(
            EscalationRow(
                escalation_id=e["id"],
                kind=e["kind"],
                state="RESOLVED" if res else "OPEN",
                claim_id=e["claim_id"],
                description=e["description"],
                resolution_outcome=res["outcome"] if res else None,
            )
        )
    open_escalations = sum(r.state == "OPEN" for r in esc_rows)

    accessed_anything = bool(sources_accessed or documents or web)
    confidence = _confidence(material, open_escalations, accessed_anything)

    # Negative-search wording: never say "nothing found" unless a source was really searched.
    # Only findings from the adverse search count here, not financial warning signs.
    adverse_claims = [c for c in claims if c.adverse and c.category == "ADVERSE_SEARCH"]
    searched = sorted(
        {
            r.source_name or r.source_key or ""
            for r in log
            if r.category == "ADVERSE_SEARCH" and r.accessed
        }
        | {
            e.origin
            for e in evidence
            if e.kind in ("WEB", "CONNECTOR") and e.evidence_type in ("NEWS", "LEGAL_REGULATORY")
        }
    )
    not_searched = sorted(
        {
            r.source_name or "no source registered"
            for r in log
            if r.category == "ADVERSE_SEARCH" and not r.accessed
        }
    )
    if adverse_claims:
        adverse_statement = (
            f"{len(adverse_claims)} adverse claim(s) were recorded. See the findings and their "
            "verification status."
        )
    elif searched:
        adverse_statement = (
            "No adverse information was found in the sources searched: "
            + ", ".join(searched)
            + ". "
            + (
                "Not searched or unavailable: " + ", ".join(not_searched) + ". "
                if not_searched
                else ""
            )
            + "This does not mean that none exists."
        )
    else:
        adverse_statement = (
            "An adverse search was not performed: no adverse-search source was accessed."
        )

    counts = Counts(
        connector_sources_accessed=len(sources_accessed),
        documents_reviewed=len(documents),
        web_sources_recorded=len(web),
        material_claims=len(material),
        verified_material_findings=len(verified_material),
        unverified_claims=len(unverified),
        information_gaps=len(gaps),
        open_escalations=open_escalations,
        unavailable_sources=len(unavailable),
    )
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    final = (
        f"As of {stamp}. Completeness: {counts.verified_material_findings} of "
        f"{counts.material_claims} material findings verified. Sources accessed through "
        f"connectors: {counts.connector_sources_accessed}; documents reviewed: "
        f"{counts.documents_reviewed}; web sources recorded by the analyst: "
        f"{counts.web_sources_recorded}. Sources unavailable: {counts.unavailable_sources}. "
        f"Information gaps: {counts.information_gaps}. Items awaiting human review: "
        f"{counts.open_escalations}. This is research for the underwriter, not an "
        "underwriting decision."
    )

    content = ReportContent(
        case_id=case_id,
        as_of=now,
        financials_reviewed=financials,
        verification_log=log,
        material_findings=[_claim_row(c) for c in material],
        unverified_claims=[_claim_row(c) for c in unverified],
        conflicts=[r for r in esc_rows if r.kind == "CONFLICT"],
        information_gaps=gaps,
        limitations=[PAYMENT_LIMITATION]
        + ([] if financials else ["No financial statements were reviewed."]),
        adverse_search_statement=adverse_statement,
        evidence_confidence=confidence,
        counts=counts,
        final_statement=final,
    )

    readiness = research_readiness(case.status, entities.open_candidate_count(case_id))
    unsupported = [
        c
        for c in material
        if c.classification.value in ("FACT", "UNVERIFIED")
        and not c.links
        and c.verification.status.value != "SOURCE_UNAVAILABLE"
    ]
    gates = [
        Gate(
            code="entity_resolved",
            passed=readiness.allowed,
            message="The legal entity is resolved."
            if readiness.allowed
            else readiness.blockers[0].message,
        ),
        Gate(
            code="no_open_escalations",
            passed=open_escalations == 0,
            message="No item is waiting for human review."
            if open_escalations == 0
            else f"{open_escalations} item(s) must be resolved by a reviewer first.",
        ),
        Gate(
            code="no_research_in_flight",
            passed=not in_flight,
            message="No research run is queued or running."
            if not in_flight
            else "A research run is still queued or running.",
        ),
        Gate(
            code="has_findings",
            passed=bool(claims or evidence),
            message="The case has recorded findings."
            if (claims or evidence)
            else "Nothing has been recorded yet: add evidence and claims first.",
        ),
        Gate(
            code="material_claims_supported",
            passed=not unsupported,
            message="Every material claim is linked to evidence or marked unavailable."
            if not unsupported
            else f"{len(unsupported)} material claim(s) have no evidence and are not marked "
            "unavailable.",
        ),
    ]
    versions: dict[str, Any] = {
        "app": request.app.version,
        "evidence_rules": claims[0].verification.rules_version if claims else None,
        "confidence_rules": confidence.rules_version,
        "connectors": connectors,
        "runs": [str(r.id) for r in runs],
    }
    return content, gates, versions
