"""Source registry endpoints against a real Postgres (TEST_DATABASE_URL; always required in CI)."""

from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_cases_api import audit, headers

SOURCES = "/api/v1/sources"


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def body(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "key": "ca-registry",
        "name": "Canadian corporate registry",
        "source_class": "OFFICIAL",
        "source_type": "company_registry",
        "jurisdictions": ["ca"],
        "access_category": "ACTUALLY_ACCESSIBLE",
        "auth_state": "NOT_REQUIRED",
    }
    base.update(kw)
    return base


def register(client: TestClient, app: FastAPI, tenant: str, **kw: Any) -> dict[str, Any]:
    r = client.post(SOURCES, json=body(**kw), headers=headers(app, "administrator", tenant))
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def test_admin_registers_a_source(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    s = register(client, db_app, tenant)
    assert s["jurisdictions"] == ["CA"]
    assert s["health"] == "UNKNOWN"
    assert s["version"] == 1
    assert "not proof" in s["notice"]
    assert "tenant_id" not in s
    events = [e for e in audit(db_app, tenant) if e.action == "source.created"]
    assert len(events) == 1
    assert events[0].details["key"] == "ca-registry"


def test_credential_fields_are_rejected(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    h = headers(db_app, "administrator", tenant)
    r = client.post(SOURCES, json=body(api_key="secret-value"), headers=h)
    assert r.status_code == 422
    assert "secret-value" not in r.text


def test_database_has_no_credential_column(db_app: FastAPI) -> None:
    engine = sa.create_engine(db_app.state.source_store._engine.url)  # noqa: SLF001
    cols = {c["name"] for c in sa.inspect(engine).get_columns("sources")}
    assert not {c for c in cols if "secret" in c or "key_" in c or "token" in c or "password" in c}


def test_accessible_source_cannot_lack_its_credential(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    h = headers(db_app, "administrator", tenant)
    r = client.post(SOURCES, json=body(auth_state="MISSING"), headers=h)
    assert r.status_code == 422
    ok = client.post(
        SOURCES,
        json=body(auth_state="MISSING", access_category="RESTRICTED_LICENSED"),
        headers=h,
    )
    assert ok.status_code == 201


@pytest.mark.parametrize(
    "bad",
    [
        {"key": "Bad Key"},
        {"jurisdictions": []},
        {"jurisdictions": ["Canada"]},
        {"access_category": "ACCESSED"},
        {"source_class": "TRUSTED"},
        {"rate_limit_per_minute": 0},
        {"name": "  "},
    ],
    ids=["key", "no-jurisdiction", "country-name", "category", "class", "rate", "blank-name"],
)
def test_invalid_entries_are_rejected(
    client: TestClient, db_app: FastAPI, tenant: str, bad: dict[str, Any]
) -> None:
    r = client.post(SOURCES, json=body(**bad), headers=headers(db_app, "administrator", tenant))
    assert r.status_code == 422


def test_duplicate_key_is_a_conflict_but_another_tenant_may_reuse_it(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    register(client, db_app, tenant)
    again = client.post(SOURCES, json=body(), headers=headers(db_app, "administrator", tenant))
    assert again.status_code == 409
    register(client, db_app, tenant + "-other")


def test_only_the_administrator_can_write(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    s = register(client, db_app, tenant)
    for role in ("underwriter", "reviewer", "research_analyst", "auditor", "service"):
        h = headers(db_app, role, tenant)
        assert client.post(SOURCES, json=body(key="x-1"), headers=h).status_code == 403
        patch = client.patch(
            f"{SOURCES}/{s['id']}", json={"expected_version": 1, "name": "x"}, headers=h
        )
        assert patch.status_code == 403


def test_readers(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    s = register(client, db_app, tenant)
    for role in ("administrator", "underwriter", "reviewer", "research_analyst", "auditor"):
        h = headers(db_app, role, tenant)
        expected = 200 if role != "auditor" else 200
        assert client.get(f"{SOURCES}/{s['id']}", headers=h).status_code == expected
    # service has neither case:read nor research... it has research:run, so it can read
    assert client.get(SOURCES, headers=headers(db_app, "service", tenant)).status_code == 200
    assert client.get(SOURCES).status_code == 401


def test_list_filters_and_global_sources(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    register(client, db_app, tenant, key="ca-reg")
    register(client, db_app, tenant, key="us-reg", jurisdictions=["US"])
    register(
        client,
        db_app,
        tenant,
        key="news",
        jurisdictions=["GLOBAL"],
        source_class="SECONDARY",
        access_category="DISCOVERY_ONLY",
    )
    h = headers(db_app, "underwriter", tenant)

    def keys(q: str) -> list[str]:
        return [s["key"] for s in client.get(SOURCES + q, headers=h).json()]

    assert keys("") == ["ca-reg", "us-reg", "news"]
    assert keys("?jurisdiction=ca") == ["ca-reg", "news"]
    assert keys("?access_category=DISCOVERY_ONLY") == ["news"]
    assert client.get(SOURCES + "?jurisdiction=Canada", headers=h).status_code == 422


def test_other_tenant_cannot_see_or_change(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    s = register(client, db_app, tenant)
    other = headers(db_app, "administrator", tenant + "-x")
    assert client.get(f"{SOURCES}/{s['id']}", headers=other).status_code == 404
    assert (
        client.patch(
            f"{SOURCES}/{s['id']}", json={"expected_version": 1, "name": "hijack"}, headers=other
        ).status_code
        == 404
    )
    assert client.get(SOURCES, headers=other).json() == []


def test_update_bumps_version_records_health_and_audits(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    s = register(client, db_app, tenant)
    h = headers(db_app, "administrator", tenant)
    r = client.patch(
        f"{SOURCES}/{s['id']}",
        json={
            "expected_version": 1,
            "health": "DOWN",
            "access_category": "TECHNICALLY_UNAVAILABLE",
        },
        headers=h,
    )
    assert r.status_code == 200
    out = r.json()
    assert (out["version"], out["health"], out["access_category"]) == (
        2,
        "DOWN",
        "TECHNICALLY_UNAVAILABLE",
    )
    assert out["health_checked_at"] is not None
    ev = [e for e in audit(db_app, tenant) if e.action == "source.updated"]
    assert ev[0].details["changed_fields"] == "access_category,health"
    assert ev[0].details["access_category"] == "TECHNICALLY_UNAVAILABLE"


def test_stale_version_and_empty_update(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    s = register(client, db_app, tenant)
    h = headers(db_app, "administrator", tenant)
    assert (
        client.patch(
            f"{SOURCES}/{s['id']}", json={"expected_version": 1, "name": "A"}, headers=h
        ).status_code
        == 200
    )
    stale = client.patch(
        f"{SOURCES}/{s['id']}", json={"expected_version": 1, "name": "B"}, headers=h
    )
    assert stale.status_code == 409
    assert client.get(f"{SOURCES}/{s['id']}", headers=h).json()["name"] == "A"
    assert (
        client.patch(f"{SOURCES}/{s['id']}", json={"expected_version": 2}, headers=h).status_code
        == 422
    )


def test_update_rules_apply_to_the_merged_result_and_key_is_fixed(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    s = register(client, db_app, tenant)
    h = headers(db_app, "administrator", tenant)
    bad = client.patch(
        f"{SOURCES}/{s['id']}", json={"expected_version": 1, "auth_state": "MISSING"}, headers=h
    )
    assert bad.status_code == 422
    rekey = client.patch(
        f"{SOURCES}/{s['id']}", json={"expected_version": 1, "key": "new-key"}, headers=h
    )
    assert rekey.status_code == 422
    cleared = client.patch(
        f"{SOURCES}/{s['id']}",
        json={"expected_version": 1, "jurisdictions": ["us", "ca", "US"]},
        headers=h,
    )
    assert cleared.json()["jurisdictions"] == ["CA", "US"]


def test_malformed_id(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    h = headers(db_app, "administrator", tenant)
    assert client.get(f"{SOURCES}/not-a-uuid", headers=h).status_code == 422
    assert (
        client.get(f"{SOURCES}/00000000-0000-0000-0000-000000000000", headers=h).status_code == 404
    )
