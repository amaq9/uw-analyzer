"""Research plan rules (pure) and research run endpoints (real Postgres)."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research.plan import Category, StepState, build_plan
from app.sources.schemas import SourceRecord
from tests.test_cases_api import audit, headers, make_case
from tests.test_draft_recommendations import resolved_case
from tests.test_sources_api import register


def src(**kw: Any) -> SourceRecord:
    base: dict[str, Any] = {
        "id": uuid.uuid4(),
        "tenant_id": "t",
        "key": "ca-registry",
        "name": "Registry",
        "source_class": "OFFICIAL",
        "source_type": "company_registry",
        "jurisdictions": ["CA"],
        "access_category": "ACTUALLY_ACCESSIBLE",
        "auth_state": "NOT_REQUIRED",
        "terms_notes": None,
        "rate_limit_per_minute": None,
        "health": "UNKNOWN",
        "health_checked_at": None,
        "version": 1,
        "created_by": "a",
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    base.update(kw)
    return SourceRecord(**base)


def by_category(plan: Any, category: Category) -> list[Any]:
    return [s for s in plan.steps if s.category is category]


# --- plan rules (pure) -----------------------------------------------------------------------


def test_empty_registry_gives_one_visible_gap_per_category() -> None:
    plan = build_plan(["CA"], [])
    assert [s.category for s in plan.steps] == list(Category)
    assert all(s.state is StepState.NOT_AVAILABLE and s.source_id is None for s in plan.steps)
    assert "No source is registered for CA" in (plan.steps[0].reason or "")


def test_accessible_source_is_planned_for_its_category_only() -> None:
    plan = build_plan(["CA"], [src()])
    registry = by_category(plan, Category.ENTITY_REGISTRY)
    assert [s.state for s in registry] == [StepState.PLANNED]
    assert by_category(plan, Category.FINANCIALS)[0].state is StepState.NOT_AVAILABLE


def test_other_jurisdictions_do_not_match_but_global_does() -> None:
    assert build_plan(["US"], [src()]).steps[0].state is StepState.NOT_AVAILABLE
    plan = build_plan(["US"], [src(jurisdictions=["GLOBAL"])])
    assert plan.steps[0].state is StepState.PLANNED


@pytest.mark.parametrize(
    ("kw", "reason"),
    [
        ({"access_category": "RESTRICTED_LICENSED", "auth_state": "MISSING"}, "licence"),
        ({"access_category": "TECHNICALLY_UNAVAILABLE"}, "technically unavailable"),
        ({"health": "DOWN"}, "down"),
    ],
    ids=["licensed", "unavailable", "down"],
)
def test_sources_that_cannot_be_used_are_listed_as_not_available(
    kw: dict[str, str], reason: str
) -> None:
    step = build_plan(["CA"], [src(**kw)]).steps[0]
    assert step.state is StepState.NOT_AVAILABLE
    assert reason in (step.reason or "").lower()
    assert step.source_id is not None  # named, not hidden (FR-2.4)


def test_discovery_only_sources_are_planned_but_flagged() -> None:
    step = build_plan(
        ["CA"],
        [src(source_type="news", access_category="DISCOVERY_ONLY", source_class="SECONDARY")],
    ).steps
    news = [s for s in step if s.source_id]
    assert {s.category for s in news} == {Category.ADVERSE_SEARCH, Category.COUNTRY_INDUSTRY}
    assert all(s.state is StepState.PLANNED and s.discovery_only for s in news)
    assert "cannot verify" in (news[0].reason or "")


def test_unknown_source_types_are_ignored_and_named() -> None:
    plan = build_plan(["CA"], [src(key="odd", source_type="mystery")])
    assert plan.ignored_sources == ["odd"]
    assert all(s.source_id is None for s in plan.steps)


def test_plan_is_deterministic() -> None:
    sources = [src(), src(key="b", source_type="news", access_category="DISCOVERY_ONLY")]
    a = [(s.category, s.state, s.reason) for s in build_plan(["CA"], sources).steps]
    b = [(s.category, s.state, s.reason) for s in build_plan(["CA"], sources).steps]
    assert a == b


# --- endpoints -------------------------------------------------------------------------------

RUNS = "/api/v1/cases/{}/research-runs"


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def test_run_is_blocked_until_the_entity_is_resolved(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    h = headers(db_app, "underwriter", tenant)
    r = client.post(RUNS.format(case["id"]), json={"jurisdictions": ["CA"]}, headers=h)
    assert r.status_code == 409
    assert "legal entity" in r.json()["error"]["message"].lower()
    assert client.get(RUNS.format(case["id"]), headers=h).json() == []
    blocked = [e for e in audit(db_app, tenant) if e.action == "research.blocked"]
    assert blocked and blocked[0].details == {"blocker": "entity_not_identified"}


def test_plan_run_records_versions_steps_and_audit(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    register(client, db_app, tenant)
    register(
        client,
        db_app,
        tenant,
        key="lic-bureau",
        source_type="financial_filings",
        source_class="COMMERCIAL",
        access_category="RESTRICTED_LICENSED",
        auth_state="MISSING",
    )
    case_id = resolved_case(client, db_app, tenant)
    h = headers(db_app, "research_analyst", tenant)
    r = client.post(RUNS.format(case_id), json={"jurisdictions": ["ca", "CA"]}, headers=h)
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "PLANNED" and run["jurisdictions"] == ["CA"]
    assert run["versions"]["policy"] == "1.1" and run["versions"]["registry"]["ca-registry"] == 1
    assert run["versions"]["model"] is None  # not run yet: nothing invented
    assert "not" in run["notice"].lower() and "accessed" in run["notice"]
    states = {(s["category"], s["state"]) for s in run["steps"]}
    assert ("ENTITY_REGISTRY", "PLANNED") in states
    assert ("FINANCIALS", "NOT_AVAILABLE") in states
    assert ("ADVERSE_SEARCH", "NOT_AVAILABLE") in states
    assert [s["ordinal"] for s in run["steps"]] == [1, 2, 3, 4]
    assert all(s["attempts"] == 0 and s["started_at"] is None for s in run["steps"])
    fin = next(s for s in run["steps"] if s["category"] == "FINANCIALS")
    assert fin["source"]["key"] == "lic-bureau" and "licence" in fin["reason"]
    event = next(e for e in audit(db_app, tenant) if e.action == "research.planned")
    assert set(event.details) == {"run_id", "steps"}
    got = client.get(f"{RUNS.format(case_id)}/{run['id']}", headers=h)
    assert got.status_code == 200 and got.json()["id"] == run["id"]


def test_the_plan_keeps_its_registry_snapshot_when_the_registry_changes(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    s = register(client, db_app, tenant)
    case_id = resolved_case(client, db_app, tenant)
    h = headers(db_app, "underwriter", tenant)
    run = client.post(RUNS.format(case_id), json={"jurisdictions": ["CA"]}, headers=h).json()
    admin = headers(db_app, "administrator", tenant)
    client.patch(
        f"/api/v1/sources/{s['id']}",
        json={"expected_version": 1, "access_category": "TECHNICALLY_UNAVAILABLE"},
        headers=admin,
    )
    again = client.get(f"{RUNS.format(case_id)}/{run['id']}", headers=h).json()
    step = next(x for x in again["steps"] if x["category"] == "ENTITY_REGISTRY")
    assert step["source"]["access_category"] == "ACTUALLY_ACCESSIBLE" and step["state"] == "PLANNED"


def test_idempotency_key_returns_the_same_run(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    h = headers(db_app, "underwriter", tenant)
    body = {"jurisdictions": ["CA"], "idempotency_key": "plan-0001-abc"}
    first = client.post(RUNS.format(case_id), json=body, headers=h)
    second = client.post(RUNS.format(case_id), json=body, headers=h)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get(RUNS.format(case_id), headers=h).json()) == 1
    other = client.post(RUNS.format(case_id), json={"jurisdictions": ["CA"]}, headers=h)
    assert other.status_code == 201 and other.json()["id"] != first.json()["id"]


@pytest.mark.parametrize(
    "bad",
    [{"jurisdictions": []}, {"jurisdictions": ["Canada"]}, {"jurisdictions": ["CA"], "x": 1}, {}],
    ids=["none", "name", "extra", "missing"],
)
def test_invalid_requests(
    client: TestClient, db_app: FastAPI, tenant: str, bad: dict[str, Any]
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    h = headers(db_app, "underwriter", tenant)
    assert client.post(RUNS.format(case_id), json=bad, headers=h).status_code == 422


def test_permissions_and_tenant_isolation(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case_id = resolved_case(client, db_app, tenant)
    ok = {"jurisdictions": ["CA"]}
    for role in ("auditor", "administrator"):
        assert (
            client.post(
                RUNS.format(case_id), json=ok, headers=headers(db_app, role, tenant)
            ).status_code
            == 403
        )
    h = headers(db_app, "underwriter", tenant)
    run = client.post(RUNS.format(case_id), json=ok, headers=h).json()
    other = headers(db_app, "underwriter", tenant + "-x")
    assert client.post(RUNS.format(case_id), json=ok, headers=other).status_code == 404
    assert client.get(RUNS.format(case_id), headers=other).status_code == 404
    assert client.get(f"{RUNS.format(case_id)}/{run['id']}", headers=other).status_code == 404
    assert client.get(f"{RUNS.format(case_id)}/{uuid.uuid4()}", headers=h).status_code == 404
    assert (
        client.get(
            f"{RUNS.format(case_id)}/{run['id']}", headers=headers(db_app, "auditor", tenant)
        ).status_code
        == 200
    )
