import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.auth.models import ROLE_PERMISSIONS, Permission, Role
from app.auth.tokens import StubIdentityProvider
from app.config import AppEnv, AuthMode, Settings
from app.main import create_app
from tests.conftest import bearer


def token(idp: StubIdentityProvider, roles: list[str], tenant: str | None = "t1", **kw: Any) -> str:
    return idp.issue(subject="user-1", tenant_id=tenant, roles=roles, **kw)


# --- authentication: deny by default ---------------------------------------------------------


def test_missing_token_is_401(client: TestClient) -> None:
    assert client.get("/api/v1/me").status_code == 401


def test_garbage_token_is_401(client: TestClient) -> None:
    assert client.get("/api/v1/me", headers=bearer("not-a-jwt")).status_code == 401


def test_valid_token_returns_principal(client: TestClient, idp: StubIdentityProvider) -> None:
    response = client.get("/api/v1/me", headers=bearer(token(idp, ["underwriter"])))
    assert response.status_code == 200
    body = response.json()
    assert body["subject"] == "user-1"
    assert body["tenant_id"] == "t1"
    assert body["roles"] == ["underwriter"]
    assert "case:write" in body["permissions"]


def test_expired_token_is_401(client: TestClient, idp: StubIdentityProvider) -> None:
    expired = token(idp, ["underwriter"], ttl_seconds=-60)
    assert client.get("/api/v1/me", headers=bearer(expired)).status_code == 401


def test_wrong_audience_is_401(client: TestClient, idp: StubIdentityProvider) -> None:
    bad = token(idp, ["underwriter"], aud="some-other-api")
    assert client.get("/api/v1/me", headers=bearer(bad)).status_code == 401


def test_wrong_issuer_is_401(client: TestClient, idp: StubIdentityProvider) -> None:
    bad = token(idp, ["underwriter"], iss="https://evil.example/")
    assert client.get("/api/v1/me", headers=bearer(bad)).status_code == 401


def test_token_signed_by_another_key_is_401(client: TestClient, idp: StubIdentityProvider) -> None:
    other = StubIdentityProvider()
    assert (
        client.get("/api/v1/me", headers=bearer(token(other, ["administrator"]))).status_code == 401
    )


def test_unsigned_alg_none_token_is_401(client: TestClient, idp: StubIdentityProvider) -> None:
    now = int(time.time())
    claims = {
        "iss": idp.issuer, "aud": idp.audience, "sub": "x", "tenant_id": "t1",
        "roles": ["administrator"], "exp": now + 300,
    }  # fmt: skip
    unsigned = jwt.encode(claims, key=None, algorithm="none")  # type: ignore[arg-type]
    assert client.get("/api/v1/me", headers=bearer(unsigned)).status_code == 401


def test_hs256_key_confusion_is_401(client: TestClient, idp: StubIdentityProvider) -> None:
    now = int(time.time())
    claims = {
        "iss": idp.issuer, "aud": idp.audience, "sub": "x", "tenant_id": "t1",
        "roles": ["administrator"], "exp": now + 300,
    }  # fmt: skip
    forged = jwt.encode(
        claims, "a-shared-secret-of-sufficient-length-0123456789", algorithm="HS256"
    )
    assert client.get("/api/v1/me", headers=bearer(forged)).status_code == 401


def test_missing_tenant_claim_is_401(client: TestClient, idp: StubIdentityProvider) -> None:
    assert (
        client.get(
            "/api/v1/me", headers=bearer(token(idp, ["underwriter"], tenant=None))
        ).status_code
        == 401
    )


def test_malformed_roles_claim_is_401(client: TestClient, idp: StubIdentityProvider) -> None:
    bad = idp.issue(subject="u", tenant_id="t1", roles="administrator")  # type: ignore[arg-type]
    assert client.get("/api/v1/me", headers=bearer(bad)).status_code == 401


def test_unknown_roles_grant_nothing(client: TestClient, idp: StubIdentityProvider) -> None:
    response = client.get("/api/v1/me", headers=bearer(token(idp, ["superuser", "god"])))
    assert response.status_code == 200
    assert response.json()["permissions"] == []


def test_rejection_message_does_not_leak_reason(
    client: TestClient, idp: StubIdentityProvider
) -> None:
    expired = token(idp, ["underwriter"], ttl_seconds=-60)
    error = client.get("/api/v1/me", headers=bearer(expired)).json()["error"]
    assert error["message"] == "Authentication required."
    assert "expired" not in str(error).lower()


# --- authorization: RBAC ---------------------------------------------------------------------


def test_reviewer_may_resolve_conflicts(client: TestClient, idp: StubIdentityProvider) -> None:
    assert (
        client.get("/_test/conflicts", headers=bearer(token(idp, ["reviewer"]))).status_code == 200
    )


@pytest.mark.parametrize(
    "role", ["underwriter", "research_analyst", "administrator", "auditor", "service"]
)
def test_other_roles_cannot_resolve_conflicts(
    client: TestClient, idp: StubIdentityProvider, role: str
) -> None:
    assert client.get("/_test/conflicts", headers=bearer(token(idp, [role]))).status_code == 403


def test_unauthenticated_cannot_reach_protected_route(client: TestClient) -> None:
    assert client.get("/_test/conflicts").status_code == 401


def test_every_role_has_a_permission_set() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)


def test_no_permission_can_make_an_underwriting_decision() -> None:
    """P-09: the system has no approve/decline/rate/limit capability to grant."""
    forbidden = ("approve", "decline", "rate", "limit", "decision", "bind")
    for permission in Permission:
        assert not any(word in permission.value for word in forbidden), permission


def test_analyst_cannot_complete_reports_and_auditor_cannot_write() -> None:
    assert Permission.REPORT_COMPLETE not in ROLE_PERMISSIONS[Role.RESEARCH_ANALYST]
    assert Permission.CASE_WRITE not in ROLE_PERMISSIONS[Role.AUDITOR]


# --- tenant isolation (AC-10) ----------------------------------------------------------------


def test_same_tenant_access_allowed(client: TestClient, idp: StubIdentityProvider) -> None:
    response = client.get(
        "/_test/cases/t1", headers=bearer(token(idp, ["underwriter"], tenant="t1"))
    )
    assert response.status_code == 200


def test_cross_tenant_access_is_denied_and_logged(
    client: TestClient, idp: StubIdentityProvider, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING", logger="uw.auth"):
        response = client.get(
            "/_test/cases/t2", headers=bearer(token(idp, ["underwriter"], tenant="t1"))
        )
    assert response.status_code == 404  # existence of other tenants' objects is not revealed
    assert "authz.cross_tenant_denied" in caplog.text


def test_permission_denial_is_logged(
    client: TestClient, idp: StubIdentityProvider, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING", logger="uw.auth"):
        client.get("/_test/conflicts", headers=bearer(token(idp, ["underwriter"])))
    assert "authz.denied" in caplog.text


# --- app wiring ------------------------------------------------------------------------------


def test_oidc_mode_wires_a_verifier_without_stub() -> None:
    app = create_app(
        Settings(
            app_env=AppEnv.PROD,
            auth_mode=AuthMode.OIDC,
            oidc_issuer="https://idp.example/",
            oidc_audience="uw-analyzer-api",
            oidc_jwks_url="https://idp.example/jwks.json",
            database_url="postgresql+psycopg://u:p@localhost/db",
        )
    )
    assert not hasattr(app.state, "stub_idp")
    assert app.state.token_verifier is not None


def test_real_key_resolver_path_accepts_a_correctly_signed_token() -> None:
    """Exercise TokenVerifier with an externally supplied public key, as OIDC mode does."""
    from app.auth.tokens import TokenVerifier

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    signed = jwt.encode(
        {
            "iss": "i",
            "aud": "a",
            "sub": "s",
            "tenant_id": "t",
            "roles": ["auditor"],
            "exp": now + 60,
        },
        key,
        algorithm="RS256",
    )
    principal = TokenVerifier(
        issuer="i", audience="a", key_resolver=lambda _t: key.public_key()
    ).verify(signed)
    assert principal.roles == {Role.AUDITOR}


def test_administrator_cannot_read_case_data() -> None:
    """Least privilege (ADR 0001): admins manage users and policy, not confidential case content."""
    assert Permission.CASE_READ not in ROLE_PERMISSIONS[Role.ADMINISTRATOR]
    assert ROLE_PERMISSIONS[Role.ADMINISTRATOR] == {Permission.ADMIN_MANAGE}


def test_administrator_is_refused_case_routes(
    client: TestClient, idp: StubIdentityProvider
) -> None:
    response = client.get("/_test/cases/t1", headers=bearer(token(idp, ["administrator"])))
    assert response.status_code == 403
