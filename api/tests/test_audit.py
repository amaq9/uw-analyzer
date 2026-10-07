import pytest
from fastapi.testclient import TestClient

from app.audit.events import Action, AuditEvent, InMemoryAuditSink, Outcome
from app.audit.recorder import new_correlation_id
from app.auth.tokens import StubIdentityProvider
from tests.conftest import bearer


def tok(idp: StubIdentityProvider, role: str, tenant: str = "t1") -> str:
    return idp.issue(subject=f"{role}-1", tenant_id=tenant, roles=[role])


# --- every denial is audited -----------------------------------------------------------------


def test_missing_token_is_audited(client: TestClient, sink: InMemoryAuditSink) -> None:
    client.get("/me")
    (event,) = sink.events
    assert event.action == Action.AUTH_REJECTED
    assert event.outcome is Outcome.DENIED
    assert event.details == {"reason": "no_token"}
    assert event.tenant_id is None and event.actor is None


def test_invalid_token_is_audited_without_leaking_it(
    client: TestClient, sink: InMemoryAuditSink
) -> None:
    client.get("/me", headers=bearer("not-a-jwt"))
    (event,) = sink.events
    assert event.action == Action.AUTH_REJECTED
    assert "not-a-jwt" not in str(event)


def test_permission_denial_is_audited(
    client: TestClient, idp: StubIdentityProvider, sink: InMemoryAuditSink
) -> None:
    client.get("/_test/conflicts", headers=bearer(tok(idp, "underwriter")))
    (event,) = sink.events
    assert event.action == Action.AUTHZ_DENIED
    assert event.tenant_id == "t1"
    assert event.actor == "underwriter-1"
    assert event.details == {"permission": "conflict:resolve"}


def test_cross_tenant_denial_is_audited_under_callers_tenant_only(
    client: TestClient, idp: StubIdentityProvider, sink: InMemoryAuditSink
) -> None:
    client.get("/_test/cases/other-tenant", headers=bearer(tok(idp, "underwriter", "t1")))
    (event,) = sink.events
    assert event.action == Action.CROSS_TENANT_DENIED
    assert event.tenant_id == "t1"
    assert event.resource_type == "case"
    assert "other-tenant" not in str(event.details)


def test_successful_requests_are_not_noise(
    client: TestClient, idp: StubIdentityProvider, sink: InMemoryAuditSink
) -> None:
    client.get("/health")
    client.get("/me", headers=bearer(tok(idp, "underwriter")))
    assert sink.events == []


def test_audit_failure_never_grants_access(
    client: TestClient, idp: StubIdentityProvider, sink: InMemoryAuditSink
) -> None:
    def boom(_event: AuditEvent) -> None:
        raise RuntimeError("database down")

    sink.record = boom  # type: ignore[assignment]
    assert client.get("/me").status_code == 401
    assert (
        client.get("/_test/conflicts", headers=bearer(tok(idp, "underwriter"))).status_code == 403
    )


# --- correlation IDs -------------------------------------------------------------------------


def test_response_carries_a_generated_request_id(client: TestClient) -> None:
    response = client.get("/health")
    assert len(response.headers["X-Request-ID"]) == 32


def test_safe_incoming_request_id_is_kept_and_stored(
    client: TestClient, sink: InMemoryAuditSink
) -> None:
    response = client.get("/me", headers={"X-Request-ID": "trace-abc-12345"})
    assert response.headers["X-Request-ID"] == "trace-abc-12345"
    assert sink.events[0].correlation_id == "trace-abc-12345"


@pytest.mark.parametrize("bad", ["short", "has space in it 123", "x" * 65, "a\nb-injection-1234"])
def test_unsafe_incoming_request_id_is_replaced(bad: str) -> None:
    assert new_correlation_id(bad) != bad


# --- GET /audit-events -----------------------------------------------------------------------


def test_audit_read_requires_the_permission(client: TestClient, idp: StubIdentityProvider) -> None:
    assert client.get("/audit-events").status_code == 401
    for role in ["underwriter", "reviewer", "research_analyst", "administrator", "service"]:
        assert client.get("/audit-events", headers=bearer(tok(idp, role))).status_code == 403


def test_auditor_sees_only_their_own_tenants_events(
    client: TestClient, idp: StubIdentityProvider
) -> None:
    client.get("/_test/conflicts", headers=bearer(tok(idp, "underwriter", "tenant-a")))
    client.get("/_test/conflicts", headers=bearer(tok(idp, "underwriter", "tenant-b")))
    events = client.get("/audit-events", headers=bearer(tok(idp, "auditor", "tenant-a"))).json()
    # Exactly tenant-a's own denial; tenant-b's event is invisible to tenant-a.
    assert [(e["action"], e["actor"]) for e in events] == [("authz.denied", "underwriter-1")]


def test_reading_the_audit_log_is_itself_audited(
    client: TestClient, idp: StubIdentityProvider, sink: InMemoryAuditSink
) -> None:
    client.get("/audit-events", headers=bearer(tok(idp, "auditor")))
    assert sink.events[-1].action == Action.AUDIT_READ
    assert sink.events[-1].outcome is Outcome.SUCCESS


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_limit_is_bounded(client: TestClient, idp: StubIdentityProvider, limit: int) -> None:
    response = client.get(f"/audit-events?limit={limit}", headers=bearer(tok(idp, "auditor")))
    assert response.status_code == 422
