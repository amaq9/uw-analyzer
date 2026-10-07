import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.deps import assert_same_tenant, require_permission
from app.auth.models import Permission, Principal
from app.auth.tokens import StubIdentityProvider
from app.config import AppEnv, AuthMode, Settings
from app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    app = create_app(Settings(app_env=AppEnv.TEST, auth_mode=AuthMode.STUB))

    # Test-only routes that exercise the permission and tenant-isolation dependencies.
    @app.get("/_test/conflicts")
    def conflicts(
        _: Principal = Depends(require_permission(Permission.CONFLICT_RESOLVE)),  # noqa: B008
    ) -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/_test/cases/{case_tenant}")
    def case(
        case_tenant: str,
        principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
    ) -> dict[str, str]:
        assert_same_tenant(principal, case_tenant)
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
