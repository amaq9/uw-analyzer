"""Case endpoints against a real Postgres (TEST_DATABASE_URL; always required in CI)."""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.audit.events import PostgresAuditSink
from app.auth.tokens import StubIdentityProvider
from app.config import AppEnv, AuthMode, Settings
from app.main import create_app
from tests.conftest import bearer

API_DIR = Path(__file__).resolve().parents[1]
CASES = "/api/v1/cases"


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
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


@pytest.fixture
def tenant() -> str:
    return f"t-{uuid.uuid4().hex[:10]}"  # a fresh tenant per test keeps tests independent


def headers(db_app: FastAPI, role: str, tenant: str) -> dict[str, str]:
    idp: StubIdentityProvider = db_app.state.stub_idp
    return bearer(idp.issue(subject=f"{role}-1", tenant_id=tenant, roles=[role]))


def make_case(client: TestClient, db_app: FastAPI, tenant: str, **fields: Any) -> dict[str, Any]:
    body = {"legal_name": "Acme Holdings Ltd", **fields}
    response = client.post(CASES, json=body, headers=headers(db_app, "underwriter", tenant))
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


def audit(db_app: FastAPI, tenant: str) -> list[Any]:
    sink: PostgresAuditSink = db_app.state.audit_sink
    return sink.list_for_tenant(tenant, 100)


# --- create ----------------------------------------------------------------------------------


def test_create_minimal_case(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case = make_case(client, db_app, tenant)
    assert case["status"] == "DRAFT"
    assert case["version"] == 1
    assert case["owner"] == "underwriter-1"
    assert "tenant_id" not in case
    assert {g["field"] for g in case["information_gaps"]} >= {"registration_number", "terms"}
    assert "legal_name" not in {g["field"] for g in case["information_gaps"]}


def test_create_full_case_has_no_gaps_and_exact_money(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(
        client,
        db_app,
        tenant,
        trading_name="Acme",
        registration_number="123456",
        jurisdiction="Ontario, Canada",
        address="1 Main St",
        website="https://acme.example",
        industry="Manufacturing",
        parent_name="Acme Group",
        exposure_amount="1250000.50",
        exposure_currency="CAD",
        terms="Net 60",
        context="Existing customer",
    )
    assert case["information_gaps"] == []
    assert case["exposure_amount"] in ("1250000.50", 1250000.5)
    assert case["exposure_currency"] == "CAD"


def test_create_without_a_name_is_rejected_and_not_saved(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    response = client.post(
        CASES, json={"industry": "x"}, headers=headers(db_app, "underwriter", tenant)
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert "legal name or a trading name" in str(error["field_errors"])
    assert client.get(CASES, headers=headers(db_app, "underwriter", tenant)).json() == []


@pytest.mark.parametrize("field", ["status", "tenant_id", "owner", "id", "version"])
def test_users_cannot_set_server_controlled_fields(
    client: TestClient, db_app: FastAPI, tenant: str, field: str
) -> None:
    response = client.post(
        CASES,
        json={"legal_name": "Acme", field: "ENTITY_RESOLVED"},
        headers=headers(db_app, "underwriter", tenant),
    )
    assert response.status_code == 422


def test_validation_errors_never_echo_what_was_submitted(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    response = client.post(
        CASES,
        json={"legal_name": "Acme", "website": "javascript:SENSITIVE-VALUE"},
        headers=headers(db_app, "underwriter", tenant),
    )
    assert response.status_code == 422
    assert "SENSITIVE-VALUE" not in response.text


# --- permissions -----------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["research_analyst", "administrator", "auditor", "service"])
def test_roles_without_case_write_cannot_create(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    response = client.post(
        CASES, json={"legal_name": "Acme"}, headers=headers(db_app, role, tenant)
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["underwriter", "reviewer", "research_analyst", "auditor"])
def test_roles_with_case_read_can_read(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    case = make_case(client, db_app, tenant)
    assert (
        client.get(f"{CASES}/{case['id']}", headers=headers(db_app, role, tenant)).status_code
        == 200
    )
    assert client.get(CASES, headers=headers(db_app, role, tenant)).status_code == 200


@pytest.mark.parametrize("role", ["administrator", "service"])
def test_administrator_and_service_cannot_read_cases(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    case = make_case(client, db_app, tenant)
    assert (
        client.get(f"{CASES}/{case['id']}", headers=headers(db_app, role, tenant)).status_code
        == 403
    )
    assert client.get(CASES, headers=headers(db_app, role, tenant)).status_code == 403


def test_unauthenticated_requests_are_refused(client: TestClient) -> None:
    assert client.get(CASES).status_code == 401
    assert client.post(CASES, json={"legal_name": "x"}).status_code == 401


# --- tenant isolation (AC-10) ----------------------------------------------------------------


def test_another_tenant_cannot_read_update_or_see_the_case(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    other = f"{tenant}-other"
    case = make_case(client, db_app, tenant)
    intruder = headers(db_app, "underwriter", other)

    assert client.get(f"{CASES}/{case['id']}", headers=intruder).status_code == 404
    patch = client.patch(
        f"{CASES}/{case['id']}",
        json={"expected_version": 1, "industry": "Hacked"},
        headers=intruder,
    )
    assert patch.status_code == 404
    assert client.get(CASES, headers=intruder).json() == []

    owner_view = client.get(f"{CASES}/{case['id']}", headers=headers(db_app, "reviewer", tenant))
    assert owner_view.json()["industry"] is None  # untouched
    assert owner_view.json()["version"] == 1


def test_cross_tenant_attempt_is_audited_without_exposing_case_data(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    other = f"{tenant}-other"
    case = make_case(client, db_app, tenant, legal_name="Very Secret Name Ltd")
    client.get(f"{CASES}/{case['id']}", headers=headers(db_app, "underwriter", other))
    events = audit(db_app, other)
    assert [e.action for e in events] == ["authz.cross_tenant_denied"]
    assert "Very Secret Name" not in str(events[0])
    assert all(e.action != "case.viewed" for e in events)


def test_missing_and_malformed_ids(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    h = headers(db_app, "underwriter", tenant)
    assert client.get(f"{CASES}/{uuid.uuid4()}", headers=h).status_code == 404
    assert client.get(f"{CASES}/not-a-uuid", headers=h).status_code == 422


# --- list ------------------------------------------------------------------------------------


def test_list_is_newest_first_paged_and_tenant_scoped(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    for name in ["First", "Second", "Third"]:
        make_case(client, db_app, tenant, legal_name=name)
    make_case(client, db_app, f"{tenant}-other", legal_name="Not mine")
    h = headers(db_app, "reviewer", tenant)

    names = [c["legal_name"] for c in client.get(CASES, headers=h).json()]
    assert names == ["Third", "Second", "First"]
    page = client.get(f"{CASES}?limit=1&offset=1", headers=h).json()
    assert [c["legal_name"] for c in page] == ["Second"]
    assert client.get(f"{CASES}?limit=0", headers=h).status_code == 422
    assert client.get(f"{CASES}?limit=101", headers=h).status_code == 422


# --- update ----------------------------------------------------------------------------------


def test_update_changes_fields_bumps_version_and_closes_gaps(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    h = headers(db_app, "underwriter", tenant)
    response = client.patch(
        f"{CASES}/{case['id']}",
        json={"expected_version": 1, "registration_number": "999", "terms": "Net 30"},
        headers=h,
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["version"] == 2
    assert updated["registration_number"] == "999"
    assert updated["legal_name"] == "Acme Holdings Ltd"  # untouched fields stay
    assert updated["updated_at"] >= case["updated_at"]
    fields = {g["field"] for g in updated["information_gaps"]}
    assert "registration_number" not in fields and "terms" not in fields


def test_stale_version_is_a_conflict_and_saves_nothing(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    h = headers(db_app, "underwriter", tenant)
    ok = client.patch(
        f"{CASES}/{case['id']}", json={"expected_version": 1, "industry": "A"}, headers=h
    )
    assert ok.status_code == 200
    stale = client.patch(
        f"{CASES}/{case['id']}", json={"expected_version": 1, "industry": "B"}, headers=h
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "conflict"
    assert "Nothing was saved" in stale.json()["error"]["message"]
    assert client.get(f"{CASES}/{case['id']}", headers=h).json()["industry"] == "A"


def test_update_rules_apply_to_the_merged_result(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)  # legal name only
    h = headers(db_app, "underwriter", tenant)
    url = f"{CASES}/{case['id']}"
    no_names = client.patch(url, json={"expected_version": 1, "legal_name": None}, headers=h)
    assert no_names.status_code == 422
    half_money = client.patch(url, json={"expected_version": 1, "exposure_amount": "5"}, headers=h)
    assert half_money.status_code == 422
    nothing = client.patch(url, json={"expected_version": 1}, headers=h)
    assert nothing.status_code == 422
    forbidden = client.patch(
        url, json={"expected_version": 1, "status": "ENTITY_RESOLVED"}, headers=h
    )
    assert forbidden.status_code == 422
    assert client.get(url, headers=h).json()["version"] == 1  # none of that saved


def test_clearing_an_optional_field_is_allowed(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant, industry="Retail")
    h = headers(db_app, "underwriter", tenant)
    response = client.patch(
        f"{CASES}/{case['id']}", json={"expected_version": 1, "industry": None}, headers=h
    )
    assert response.status_code == 200 and response.json()["industry"] is None


def test_read_only_roles_cannot_update(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case = make_case(client, db_app, tenant)
    for role in ["research_analyst", "auditor", "administrator"]:
        response = client.patch(
            f"{CASES}/{case['id']}",
            json={"expected_version": 1, "industry": "x"},
            headers=headers(db_app, role, tenant),
        )
        assert response.status_code == 403


# --- audit (FR-1.7) --------------------------------------------------------------------------


def test_create_view_and_update_are_audited_without_case_content(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant, legal_name="Totally Confidential Corp")
    h = headers(db_app, "underwriter", tenant)
    client.get(f"{CASES}/{case['id']}", headers=h)
    client.patch(
        f"{CASES}/{case['id']}",
        json={"expected_version": 1, "terms": "Net 45 secret terms"},
        headers=h,
    )
    events = list(reversed(audit(db_app, tenant)))  # oldest first
    assert [e.action for e in events] == ["case.created", "case.viewed", "case.updated"]
    assert all(e.resource_id == case["id"] and e.resource_type == "case" for e in events)
    assert events[2].details == {"changed_fields": "terms", "new_version": "2"}
    everything = " ".join(str(e) for e in events)
    assert "Totally Confidential" not in everything and "secret terms" not in everything


def test_listing_cases_is_not_audited_per_case(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    make_case(client, db_app, tenant)
    before = len(audit(db_app, tenant))
    client.get(CASES, headers=headers(db_app, "underwriter", tenant))
    assert len(audit(db_app, tenant)) == before


# --- P-09 ------------------------------------------------------------------------------------


def test_no_case_field_or_path_can_carry_a_decision(db_app: FastAPI) -> None:
    banned = ("approv", "declin", "rating", "score", "decision", "credit_limit", "bind")
    schema = db_app.openapi()
    names = [p for p in schema["paths"]]
    for model in schema["components"]["schemas"].values():
        names += list(model.get("properties", {}))
    assert not [n for n in names if any(word in n.lower() for word in banned)]
