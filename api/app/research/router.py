"""Research run endpoints (FR-2.3, FR-2.5, FR-2.6). Creating a run builds a plan from the case and
the source registry; starting it queues it for the worker. Substantive research is blocked until
the legal entity is resolved (P-03), checked on the server every time. Each run records the
versions it was made with (P-10). "Accessed" is derived only from the connector-call log."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app import __version__
from app.audit.events import Action, Outcome
from app.audit.recorder import correlation_id_of, record_event
from app.auth.deps import require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.cases.entities import ResearchBlockedError, require_research_allowed, research_readiness
from app.cases.entity_store import PostgresEntityStore
from app.cases.schemas import CaseStatus
from app.recommendation.policy import POLICY_VERSION
from app.research.plan import PLAN_RULES_VERSION, build_plan
from app.research.run_store import PostgresRunQueue
from app.research.schemas import CallOut, RunCreate, RunOut, RunRecord, call_out, to_out
from app.research.store import PostgresResearchStore
from app.sources.store import PostgresSourceStore

router = APIRouter(prefix="/cases", tags=["research"])


def _store(request: Request) -> PostgresResearchStore:
    store: PostgresResearchStore = request.app.state.research_store
    return store


def _queue(request: Request) -> PostgresRunQueue:
    queue: PostgresRunQueue = request.app.state.run_queue
    return queue


def _out(request: Request, run: RunRecord) -> RunOut:
    # "Accessed" comes only from the call log: a step counts only if an executed call succeeded.
    accessed = {c.step_id for c in _queue(request).calls_for_run(run.id) if c.outcome == "SUCCESS"}
    return to_out(run, _store(request).steps_for_run(run.id), accessed)


def _load_run(
    request: Request, principal: Principal, case_id: uuid.UUID, run_id: uuid.UUID
) -> RunRecord:
    load_case_for(request, principal, case_id)
    run = _store(request).get_run(run_id)
    if run is None or run.case_id != case_id or run.tenant_id != principal.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research run not found.")
    return run


def _check_research_allowed(
    request: Request, principal: Principal, case_id: uuid.UUID, case_status: CaseStatus
) -> None:
    entities: PostgresEntityStore = request.app.state.entity_store
    readiness = research_readiness(case_status, entities.open_candidate_count(case_id))
    try:
        require_research_allowed(readiness)
    except ResearchBlockedError as exc:
        record_event(
            request,
            Action.RESEARCH_BLOCKED,
            Outcome.DENIED,
            tenant_id=principal.tenant_id,
            actor=principal.subject,
            resource_type="case",
            resource_id=str(case_id),
            details={"blocker": exc.readiness.blockers[0].code},
        )
        raise HTTPException(status.HTTP_409_CONFLICT, exc.readiness.blockers[0].message) from None


@router.post("/{case_id}/research-runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(
    request: Request,
    response: Response,
    case_id: uuid.UUID,
    body: RunCreate,
    principal: Principal = Depends(require_permission(Permission.RESEARCH_RUN)),  # noqa: B008
) -> RunOut:
    """Plan research for the case. Blocked until the entity is resolved. Sending the same
    `idempotency_key` again returns the run already made (200) instead of making another."""
    case = load_case_for(request, principal, case_id)
    _check_research_allowed(request, principal, case_id, case.status)

    if body.idempotency_key:
        existing = _store(request).find_by_idempotency_key(case_id, body.idempotency_key)
        if existing:
            response.status_code = status.HTTP_200_OK
            return _out(request, existing)

    sources: PostgresSourceStore = request.app.state.source_store
    registry = sources.list_for_tenant(principal.tenant_id)
    plan = build_plan(body.jurisdictions, registry)
    versions = {
        "app": __version__,
        "plan_rules": PLAN_RULES_VERSION,
        "policy": POLICY_VERSION,
        # Filled in by later steps as they run: prompt, model, connectors (P-10).
        "prompt": None,
        "model": None,
        "connectors": {},
        "registry": {s.key: s.version for s in registry},
        "ignored_sources": plan.ignored_sources,
    }
    run = _store(request).create_run(
        case_id=case_id,
        tenant_id=principal.tenant_id,
        jurisdictions=body.jurisdictions,
        versions=versions,
        idempotency_key=body.idempotency_key,
        correlation_id=correlation_id_of(request),
        created_by=principal.subject,
        steps=plan.steps,
    )
    record_event(
        request,
        Action.RESEARCH_PLANNED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        details={"run_id": str(run.id), "steps": str(len(plan.steps))},
    )
    return _out(request, run)


@router.get("/{case_id}/research-runs", response_model=list[RunOut])
def list_runs(
    request: Request,
    case_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[RunOut]:
    load_case_for(request, principal, case_id)
    return [_out(request, r) for r in _store(request).list_runs(case_id, principal.tenant_id)]


@router.get("/{case_id}/research-runs/{run_id}", response_model=RunOut)
def get_run(
    request: Request,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> RunOut:
    return _out(request, _load_run(request, principal, case_id, run_id))


@router.post("/{case_id}/research-runs/{run_id}/start", response_model=RunOut)
def start_run(
    request: Request,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.RESEARCH_RUN)),  # noqa: B008
) -> RunOut:
    """Queue a planned run for the worker. A run with failed steps (FAILED, or COMPLETED where only
    discovery-only sources failed) can be queued again to resume: finished steps are not repeated.
    The entity gate is checked again here (the entity may have been reopened since planning)."""
    run = _load_run(request, principal, case_id, run_id)
    case = load_case_for(request, principal, case_id)
    _check_research_allowed(request, principal, case_id, case.status)
    if not _queue(request).queue(run_id):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This run is {run.status.value.lower()} and cannot be started. Only a planned run, "
            "or a run with failed steps, can be queued.",
        )
    record_event(
        request,
        Action.RESEARCH_STARTED,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        details={"run_id": str(run_id)},
    )
    return _out(request, _load_run(request, principal, case_id, run_id))


@router.get("/{case_id}/research-runs/{run_id}/connector-calls", response_model=list[CallOut])
def list_connector_calls(
    request: Request,
    case_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> list[CallOut]:
    """Every connector call this run made, in order. Read-only: nothing can add to this log
    except an executed call."""
    _load_run(request, principal, case_id, run_id)
    return [call_out(c) for c in _queue(request).calls_for_run(run_id)]
