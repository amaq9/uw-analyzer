import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.tokens import StubIdentityProvider
from tests.conftest import bearer

SHAPE = {"code", "message", "correlation_id", "retryable"}


def test_401_uses_the_standard_error_object(client: TestClient) -> None:
    response = client.get("/api/v1/me", headers={"X-Request-ID": "trace-abc-12345"})
    assert response.status_code == 401
    error = response.json()["error"]
    assert set(error) >= SHAPE
    assert error["code"] == "unauthenticated"
    assert error["correlation_id"] == "trace-abc-12345"
    assert error["retryable"] is False
    assert response.headers["X-Request-ID"] == "trace-abc-12345"


def test_403_and_404_codes(client: TestClient, idp: StubIdentityProvider) -> None:
    token = idp.issue(subject="u", tenant_id="t1", roles=["underwriter"])
    forbidden = client.get("/api/v1/audit-events", headers=bearer(token))
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"
    assert client.get("/nope").json()["error"]["code"] == "not_found"
    assert client.post("/health").json()["error"]["code"] == "method_not_allowed"


def test_validation_error_lists_fields_and_never_echoes_input(
    client: TestClient, idp: StubIdentityProvider
) -> None:
    token = idp.issue(subject="a", tenant_id="t1", roles=["auditor"])
    submitted = "SENSITIVE-CASE-TEXT"
    response = client.get(f"/api/v1/audit-events?limit={submitted}", headers=bearer(token))
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["field_errors"][0]["field"] == "limit"
    assert submitted not in response.text
    assert "Nothing was saved" in error["message"]


def test_unexpected_exception_is_generic_and_leaks_nothing(
    app: FastAPI, idp: StubIdentityProvider
) -> None:
    @app.get("/_test/boom")
    def boom() -> None:
        raise RuntimeError("db password is hunter2")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/_test/boom", headers={"X-Request-ID": "trace-boom-12345"})
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "hunter2" not in response.text and "RuntimeError" not in response.text
    assert error["correlation_id"] == "trace-boom-12345"
    assert response.headers["X-Request-ID"] == "trace-boom-12345"


@pytest.mark.parametrize("path", ["/api/v1/me", "/api/v1/audit-events"])
def test_endpoints_live_under_api_v1_only(client: TestClient, path: str) -> None:
    assert client.get(path.removeprefix("/api/v1")).status_code == 404
    assert client.get(path).status_code == 401


def test_health_stays_unversioned(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
