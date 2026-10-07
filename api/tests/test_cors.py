import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import AppEnv, AuthMode, Settings
from app.main import create_app
from tests.conftest import DUMMY_DB_URL

UI = "http://localhost:3000"


def make_client(origins: list[str]) -> TestClient:
    settings = Settings(
        app_env=AppEnv.TEST,
        auth_mode=AuthMode.STUB,
        database_url=DUMMY_DB_URL,
        cors_allowed_origins=origins,
    )
    return TestClient(create_app(settings))


def preflight(client: TestClient, origin: str) -> object:
    return client.options(
        "/api/v1/me",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )


def test_no_origins_means_no_cors_headers() -> None:
    response = make_client([]).get("/health", headers={"Origin": UI})
    assert "access-control-allow-origin" not in response.headers


def test_allowed_origin_may_preflight_and_read_request_id() -> None:
    client = make_client([UI])
    pre = preflight(client, UI)
    assert pre.status_code == 200  # type: ignore[attr-defined]
    assert pre.headers["access-control-allow-origin"] == UI  # type: ignore[attr-defined]
    assert "authorization" in pre.headers["access-control-allow-headers"].lower()  # type: ignore[attr-defined]
    real = client.get("/health", headers={"Origin": UI})
    assert real.headers["access-control-allow-origin"] == UI
    assert "x-request-id" in real.headers["access-control-expose-headers"].lower()


def test_other_origin_is_refused() -> None:
    client = make_client([UI])
    pre = preflight(client, "https://evil.example")
    assert "access-control-allow-origin" not in pre.headers  # type: ignore[attr-defined]
    real = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in real.headers


def test_credentials_are_never_allowed() -> None:
    pre = preflight(make_client([UI]), UI)
    assert "access-control-allow-credentials" not in pre.headers  # type: ignore[attr-defined]


def test_preflight_does_not_hit_auth_or_the_audit_log() -> None:
    client = make_client([UI])
    assert preflight(client, UI).status_code == 200  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "bad",
    ["*", "http://localhost:3000/", "https://app.example.com/path", "localhost:3000", "ftp://x"],
)
def test_wildcards_paths_and_odd_origins_are_rejected(bad: str) -> None:
    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        Settings(
            app_env=AppEnv.TEST,
            auth_mode=AuthMode.STUB,
            database_url=DUMMY_DB_URL,
            cors_allowed_origins=[bad],
        )


@pytest.mark.parametrize("env", [AppEnv.STAGING, AppEnv.PROD])
def test_plain_http_origin_is_rejected_in_staging_and_prod(env: AppEnv) -> None:
    with pytest.raises(ValidationError, match="https"):
        Settings(
            app_env=env,
            database_url=DUMMY_DB_URL,
            oidc_issuer="https://idp.example/",
            oidc_audience="a",
            oidc_jwks_url="https://idp.example/jwks.json",
            cors_allowed_origins=["http://app.example.com"],
        )
