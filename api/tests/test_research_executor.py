"""Research executor, call log and worker against a real Postgres. The connectors here are test
doubles that exist only in tests: the product ships none, and never simulates one."""

import time
import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from app.research.connectors import (
    ConnectorRequest,
    ConnectorResult,
    ConnectorSet,
    PermanentConnectorError,
    RetryableConnectorError,
)
from app.research.executor import Executor
from scripts import worker
from tests.test_cases_api import audit, headers
from tests.test_draft_recommendations import resolved_case
from tests.test_sources_api import register


class Fake:
    version = "test-1"

    def __init__(self, key: str, plan: list[Any]) -> None:
        self.key = key
        self.plan = list(plan)  # each item: "ok", "retry", "permanent", "empty", "slow"
        self.calls = 0

    def describe(self, request: ConnectorRequest) -> str:
        return "Test lookup"

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        self.calls += 1
        action = self.plan.pop(0) if len(self.plan) > 1 else self.plan[0]
        if action == "retry":
            raise RetryableConnectorError
        if action == "permanent":
            raise PermanentConnectorError
        if action == "slow":
            time.sleep(0.4)
        if action == "empty":
            return ConnectorResult(provenance_ref="  ")
        return ConnectorResult(provenance_ref=f"snapshot://{uuid.uuid4()}", items=1)


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def executor(app: FastAPI, *connectors: Fake, timeout: float = 5.0) -> tuple[Executor, list[float]]:
    sleeps: list[float] = []
    ex = Executor(
        runs=app.state.research_store,
        queue=app.state.run_queue,
        sources=app.state.source_store,
        cases=app.state.case_store,
        connectors=ConnectorSet({c.key: c for c in connectors}),
        timeout_seconds=timeout,
        backoff_seconds=1.0,
        sleep=sleeps.append,
    )
    return ex, sleeps


def drain(ex: Executor) -> None:
    while ex.work_once():
        pass


def setup_run(
    client: TestClient, app: FastAPI, tenant: str, *sources: dict[str, Any]
) -> tuple[str, str, dict[str, str]]:
    for extra in sources:
        register(client, app, tenant, **extra)
    case_id = resolved_case(client, app, tenant)
    h = headers(app, "underwriter", tenant)
    run = client.post(
        f"/api/v1/cases/{case_id}/research-runs", json={"jurisdictions": ["CA"]}, headers=h
    )
    return case_id, run.json()["id"], h


def start(client: TestClient, case_id: str, run_id: str, h: dict[str, str]) -> Any:
    return client.post(f"/api/v1/cases/{case_id}/research-runs/{run_id}/start", headers=h)


def get_run(client: TestClient, case_id: str, run_id: str, h: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = client.get(
        f"/api/v1/cases/{case_id}/research-runs/{run_id}", headers=h
    ).json()
    return out


def calls(client: TestClient, case_id: str, run_id: str, h: dict[str, str]) -> list[dict[str, Any]]:
    url = f"/api/v1/cases/{case_id}/research-runs/{run_id}/connector-calls"
    out: list[dict[str, Any]] = client.get(url, headers=h).json()
    return out


def step(run: dict[str, Any], category: str) -> dict[str, Any]:
    return next(s for s in run["steps"] if s["category"] == category)


def test_without_a_connector_the_step_is_skipped_and_nothing_is_claimed(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    assert start(client, case_id, run_id, h).json()["status"] == "QUEUED"
    ex, _ = executor(db_app)
    drain(ex)
    run = get_run(client, case_id, run_id, h)
    reg = step(run, "ENTITY_REGISTRY")
    assert run["status"] == "COMPLETED"
    assert reg["state"] == "SKIPPED" and "No connector is implemented" in reg["reason"]
    assert reg["accessed"] is False
    assert calls(client, case_id, run_id, h) == []


def test_successful_call_is_logged_with_provenance_and_marks_the_step_accessed(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    start(client, case_id, run_id, h)
    fake = Fake(key, ["ok"])
    drain(executor(db_app, fake)[0])
    run = get_run(client, case_id, run_id, h)
    reg = step(run, "ENTITY_REGISTRY")
    assert (reg["state"], reg["accessed"], reg["attempts"]) == ("SUCCEEDED", True, 1)
    assert run["versions"]["connectors"] == {key: "test-1"}  # P-10
    log = calls(client, case_id, run_id, h)
    assert len(log) == 1
    assert log[0]["outcome"] == "SUCCESS" and log[0]["provenance_ref"].startswith("snapshot://")
    assert log[0]["access_status"] == "ACTUALLY_ACCESSIBLE" and log[0]["action"] == "Test lookup"
    assert log[0]["started_at"] <= log[0]["ended_at"]
    assert run["status"] == "COMPLETED" and run["started_at"] and run["completed_at"]


def test_retryable_errors_back_off_and_then_succeed(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    start(client, case_id, run_id, h)
    ex, sleeps = executor(db_app, Fake(key, ["retry", "retry", "ok"]))
    drain(ex)
    log = calls(client, case_id, run_id, h)
    assert [c["outcome"] for c in log] == ["ERROR", "ERROR", "SUCCESS"]
    assert [c["error_class"] for c in log] == ["retryable", "retryable", None]
    assert sleeps == [1.0, 2.0]
    assert step(get_run(client, case_id, run_id, h), "ENTITY_REGISTRY")["attempts"] == 3


def test_attempts_are_bounded_and_a_failed_run_can_resume(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    start(client, case_id, run_id, h)
    drain(executor(db_app, Fake(key, ["retry"]))[0])
    run = get_run(client, case_id, run_id, h)
    reg = step(run, "ENTITY_REGISTRY")
    assert (run["status"], reg["state"], reg["attempts"]) == ("FAILED", "FAILED", 3)
    assert len(calls(client, case_id, run_id, h)) == 3
    assert reg["accessed"] is False

    assert start(client, case_id, run_id, h).status_code == 200  # FAILED -> QUEUED (resume)
    drain(executor(db_app, Fake(key, ["ok"]))[0])
    run = get_run(client, case_id, run_id, h)
    assert run["status"] == "COMPLETED"
    reg = step(run, "ENTITY_REGISTRY")
    assert (reg["state"], reg["attempts"], reg["accessed"]) == ("SUCCEEDED", 4, True)
    assert [c["attempt"] for c in calls(client, case_id, run_id, h)] == [1, 2, 3, 4]


def test_finished_steps_are_not_repeated_on_resume(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    reg_key, fin_key = f"r-{tenant}", f"f-{tenant}"
    case_id, run_id, h = setup_run(
        client,
        db_app,
        tenant,
        {"key": reg_key},
        {"key": fin_key, "source_type": "financial_filings", "source_class": "COMMERCIAL"},
    )
    start(client, case_id, run_id, h)
    reg, fin = Fake(reg_key, ["ok"]), Fake(fin_key, ["permanent"])
    drain(executor(db_app, reg, fin)[0])
    assert (reg.calls, fin.calls) == (1, 1)  # permanent error: no retries
    assert get_run(client, case_id, run_id, h)["status"] == "FAILED"

    start(client, case_id, run_id, h)
    fin2 = Fake(fin_key, ["ok"])
    drain(executor(db_app, reg, fin2)[0])
    assert (reg.calls, fin2.calls) == (1, 1)  # the registry step was not run again
    assert get_run(client, case_id, run_id, h)["status"] == "COMPLETED"


def test_timeout_is_recorded_and_retried(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    start(client, case_id, run_id, h)
    drain(executor(db_app, Fake(key, ["slow"]), timeout=0.05)[0])
    log = calls(client, case_id, run_id, h)
    assert [c["outcome"] for c in log] == ["TIMEOUT"] * 3
    assert log[0]["provenance_ref"] is None
    assert get_run(client, case_id, run_id, h)["status"] == "FAILED"


def test_a_result_without_provenance_never_counts_as_access(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    start(client, case_id, run_id, h)
    drain(executor(db_app, Fake(key, ["empty"]))[0])
    log = calls(client, case_id, run_id, h)
    assert {c["outcome"] for c in log} == {"ERROR"} and log[0]["error_class"] == "no_provenance"
    assert step(get_run(client, case_id, run_id, h), "ENTITY_REGISTRY")["accessed"] is False


def test_a_source_withdrawn_after_planning_is_skipped(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    source = client.get("/api/v1/sources", headers=headers(db_app, "administrator", tenant)).json()[
        0
    ]
    client.patch(
        f"/api/v1/sources/{source['id']}",
        json={"expected_version": 1, "access_category": "TECHNICALLY_UNAVAILABLE"},
        headers=headers(db_app, "administrator", tenant),
    )
    start(client, case_id, run_id, h)
    fake = Fake(key, ["ok"])
    drain(executor(db_app, fake)[0])
    assert fake.calls == 0
    assert step(get_run(client, case_id, run_id, h), "ENTITY_REGISTRY")["state"] == "SKIPPED"


def test_start_rules(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case_id, run_id, h = setup_run(client, db_app, tenant)
    assert start(client, case_id, run_id, headers(db_app, "auditor", tenant)).status_code == 403
    assert (
        start(client, case_id, run_id, headers(db_app, "underwriter", tenant + "-x")).status_code
        == 404
    )
    assert start(client, case_id, run_id, h).status_code == 200
    again = start(client, case_id, run_id, h)
    assert again.status_code == 409 and "queued" in again.json()["error"]["message"]
    drain(executor(db_app)[0])
    assert start(client, case_id, run_id, h).status_code == 409  # COMPLETED cannot restart
    events = [e.action for e in audit(db_app, tenant)]
    assert events.count("research.started") == 1


def test_start_rechecks_the_entity_gate(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case_id, run_id, h = setup_run(client, db_app, tenant)
    reopened = client.post(
        f"/api/v1/cases/{case_id}/entity-resolution/reopen", json={"reason": "New facts"}, headers=h
    )
    assert reopened.status_code == 200, reopened.text
    blocked = start(client, case_id, run_id, h)
    assert (
        blocked.status_code == 409 and "legal entit" in blocked.json()["error"]["message"].lower()
    )
    assert get_run(client, case_id, run_id, h)["status"] == "PLANNED"


def test_the_call_log_is_append_only_and_has_no_write_api(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    start(client, case_id, run_id, h)
    drain(executor(db_app, Fake(key, ["ok"]))[0])
    url = f"/api/v1/cases/{case_id}/research-runs/{run_id}/connector-calls"
    assert client.post(url, json={}, headers=h).status_code == 405
    assert client.put(url, json={}, headers=h).status_code == 405
    engine = db_app.state.run_queue._engine
    for sql in (
        "UPDATE connector_calls SET outcome = 'ERROR'",
        "DELETE FROM connector_calls",
        "TRUNCATE connector_calls",
    ):
        with pytest.raises(DBAPIError), engine.begin() as conn:
            conn.execute(sa.text(sql))


def test_the_database_refuses_success_without_provenance(db_app: FastAPI) -> None:
    engine = db_app.state.run_queue._engine
    with pytest.raises(DBAPIError, match="success_has_provenance"), engine.begin() as conn:
        conn.execute(sa.text("SET session_replication_role = replica"))  # skip FKs, keep CHECKs
        conn.execute(
            sa.text(
                "INSERT INTO connector_calls (id, tenant_id, case_id, run_id, step_id, source_id, "
                "source_key, connector_version, attempt, action, access_status, started_at, "
                "ended_at, outcome, provenance_ref) VALUES (:i, 't', :i, :i, :i, :i, 'k', 'v', 1, "
                "'a', 'ACTUALLY_ACCESSIBLE', now(), now(), 'SUCCESS', NULL)"
            ),
            {"i": uuid.uuid4()},
        )


def test_a_claimed_run_is_not_claimed_twice(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, run_id, h = setup_run(client, db_app, tenant)
    start(client, case_id, run_id, h)
    queue = db_app.state.run_queue
    first = queue.claim_next()
    assert first is not None and str(first.id) == run_id and first.status.value == "RUNNING"
    second = queue.claim_next()
    assert second is None or str(second.id) != run_id
    queue.finish_run(first.id, "COMPLETED", first.versions)


def test_a_crashed_connector_fails_the_step_without_stopping_the_worker(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    start(client, case_id, run_id, h)

    class Crashing(Fake):
        def execute(self, request: ConnectorRequest) -> ConnectorResult:
            raise ValueError("boom")

    drain(executor(db_app, Crashing(key, ["ok"]))[0])
    log = calls(client, case_id, run_id, h)
    assert {c["error_class"] for c in log} == {"permanent"} and len(log) == 1
    assert get_run(client, case_id, run_id, h)["status"] == "FAILED"


def test_worker_script_once_drains_the_queue(
    client: TestClient,
    db_app: FastAPI,
    database_url: str,
    tenant: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in (("APP_ENV", "test"), ("AUTH_MODE", "stub")):
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DATABASE_URL", database_url)
    case_id, run_id, h = setup_run(client, db_app, tenant)
    start(client, case_id, run_id, h)
    assert worker.main(["--once"]) == 0
    assert get_run(client, case_id, run_id, h)["status"] == "COMPLETED"
    assert uuid.UUID(run_id)
