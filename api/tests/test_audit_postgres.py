"""Integration tests against a real Postgres (set TEST_DATABASE_URL; always required in CI)."""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

from app.audit.events import Action, AuditEvent, Outcome, PostgresAuditSink, audit_events
from app.auth.tokens import StubIdentityProvider
from app.config import AppEnv, AuthMode, Settings
from app.main import create_app
from tests.conftest import bearer

API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("CI"):
            pytest.fail("TEST_DATABASE_URL must be set in CI")
        pytest.skip("TEST_DATABASE_URL not set; skipping Postgres integration tests")
    return url


@pytest.fixture
def engine(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    monkeypatch.setenv("DATABASE_URL", database_url)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    eng = sa.create_engine(database_url)
    yield eng
    eng.dispose()


def _event(tenant: str = "t1", action: str = "authz.denied") -> AuditEvent:
    return AuditEvent(
        action=action,
        outcome=Outcome.DENIED,
        correlation_id="corr-1234567",
        tenant_id=tenant,
        actor="u1",
        details={"permission": "case:write"},
    )


def test_event_round_trips(engine: Engine) -> None:
    sink = PostgresAuditSink(engine)
    sink.record(_event())
    (got,) = sink.list_for_tenant("t1", 10)
    assert got.action == "authz.denied"
    assert got.details == {"permission": "case:write"}
    assert got.occurred_at.tzinfo is not None


def test_list_is_tenant_scoped_and_newest_first(engine: Engine) -> None:
    sink = PostgresAuditSink(engine)
    first, second = _event("t1", "a.first"), _event("t1", "a.second")
    sink.record(first)
    sink.record(second)
    sink.record(_event("t2", "b.other"))
    assert [e.action for e in sink.list_for_tenant("t1", 10)] == ["a.second", "a.first"]
    assert [e.action for e in sink.list_for_tenant("t2", 10)] == ["b.other"]
    assert len(sink.list_for_tenant("t1", 1)) == 1


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET action = 'tampered'",
        "DELETE FROM audit_events",
        "TRUNCATE audit_events",
    ],
)
def test_database_refuses_to_change_or_remove_events(engine: Engine, statement: str) -> None:
    PostgresAuditSink(engine).record(_event())
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(sa.text(statement))
    with engine.connect() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(audit_events)).scalar() == 1


def test_duplicate_event_id_is_rejected(engine: Engine) -> None:
    sink = PostgresAuditSink(engine)
    event = _event()
    sink.record(event)
    with pytest.raises(DBAPIError):
        sink.record(event)


def test_migration_downgrade_and_upgrade_are_reversible(
    engine: Engine, database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "migrations"))
    command.downgrade(cfg, "base")
    assert not sa.inspect(engine).has_table("audit_events")
    command.upgrade(cfg, "head")
    assert sa.inspect(engine).has_table("audit_events")


def test_end_to_end_denials_are_persisted_per_tenant(engine: Engine, database_url: str) -> None:
    settings = Settings(app_env=AppEnv.TEST, auth_mode=AuthMode.STUB, database_url=database_url)
    app = create_app(settings)
    client = TestClient(app)
    idp: StubIdentityProvider = app.state.stub_idp
    rid = f"req-{uuid.uuid4().hex[:12]}"

    def token(role: str, tenant: str) -> str:
        return idp.issue(subject=f"{role}-1", tenant_id=tenant, roles=[role])

    client.get("/me", headers={"X-Request-ID": rid})  # unauthenticated
    # Permission denial for tenant-a, via the audit endpoint's own permission check.
    client.get("/audit-events", headers=bearer(token("underwriter", "tenant-a")))
    client.get("/audit-events", headers=bearer(token("underwriter", "tenant-b")))

    seen = client.get("/audit-events", headers=bearer(token("auditor", "tenant-a"))).json()
    # tenant-a's auditor sees only tenant-a's single denial, not tenant-b's.
    assert [e["action"] for e in seen] == [Action.AUTHZ_DENIED.value]
    # The unauthenticated event has no tenant, so no tenant can read it, but it is stored.
    with engine.connect() as conn:
        stored = conn.execute(
            sa.select(audit_events.c.correlation_id).where(audit_events.c.tenant_id.is_(None))
        ).scalars()
        assert rid in list(stored)
