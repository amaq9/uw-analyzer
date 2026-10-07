import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.audit.events import InMemoryAuditSink
from app.auth.deps import assert_same_tenant, require_permission
from app.auth.models import Permission, Principal
from app.auth.tokens import StubIdentityProvider
from app.config import AppEnv, AuthMode, Settings
from app.main import create_app

DUMMY_DB_URL = "postgresql+psycopg://unused:unused@localhost:1/unused"  # engine never connects


@pytest.fixture
def sink() -> InMemoryAuditSink:
    return InMemoryAuditSink()


@pytest.fixture
def app(sink: InMemoryAuditSink) -> FastAPI:
    settings = Settings(app_env=AppEnv.TEST, auth_mode=AuthMode.STUB, database_url=DUMMY_DB_URL)
    app = create_app(settings, audit_sink=sink)

    # Test-only routes that exercise the permission and tenant-isolation dependencies.
    @app.get("/_test/conflicts")
    def conflicts(
        _: Principal = Depends(require_permission(Permission.CONFLICT_RESOLVE)),  # noqa: B008
    ) -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/_test/cases/{case_tenant}")
    def case(
        request: Request,
        case_tenant: str,
        principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
    ) -> dict[str, str]:
        assert_same_tenant(request, principal, case_tenant, resource_type="case")
        return {"tenant": case_tenant}

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def idp(app: FastAPI) -> StubIdentityProvider:
    stub: StubIdentityProvider = app.state.stub_idp
    return stub


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- shared Postgres fixtures (integration tests; always required in CI) ----------------------

API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        if os.environ.get("CI"):
            pytest.fail("TEST_DATABASE_URL must be set in CI")
        pytest.skip("TEST_DATABASE_URL not set; skipping Postgres integration tests")
    return url


@pytest.fixture(scope="module")
def db_app(database_url: str) -> Iterator[FastAPI]:
    with pytest.MonkeyPatch.context() as mp:  # set for the migration, restored afterwards
        mp.setenv("DATABASE_URL", database_url)
        cfg = Config(str(API_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_DIR / "migrations"))
        command.upgrade(cfg, "head")
    settings = Settings(app_env=AppEnv.TEST, auth_mode=AuthMode.STUB, database_url=database_url)
    yield create_app(settings)


@pytest.fixture
def tenant() -> str:
    return f"t-{uuid.uuid4().hex[:10]}"  # a fresh tenant per test keeps tests independent
