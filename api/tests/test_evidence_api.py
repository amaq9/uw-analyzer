"""Evidence, claims and computed verification against a real Postgres."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from tests.test_cases_api import audit, headers
from tests.test_draft_recommendations import resolved_case
from tests.test_research_executor import Fake, calls, drain, executor, setup_run, start

NOW = datetime.now(UTC)


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def web(**kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "kind": "WEB",
        "evidence_type": "LEGAL_REGULATORY",
        "title": "Court judgment",
        "origin": "Courts.Example.org",
        "excerpt": "Judgment entered against the company.",
        "source_class": "OFFICIAL",
        "is_primary": True,
        "url": "https://courts.example.org/j/1",
        "retrieved_at": (NOW - timedelta(minutes=5)).isoformat(),
        "event_on": (NOW - timedelta(days=20)).date().isoformat(),
    }
    body.update(kw)
    return body


class Ctx:
    def __init__(self, client: TestClient, app: FastAPI, tenant: str, case_id: str) -> None:
        self.client, self.app, self.tenant, self.case_id = client, app, tenant, case_id
        self.h = headers(app, "underwriter", tenant)

    def url(self, tail: str) -> str:
        return f"/api/v1/cases/{self.case_id}/{tail}"

    def evidence(self, **kw: Any) -> dict[str, Any]:
        r = self.client.post(self.url("evidence"), json=web(**kw), headers=self.h)
        assert r.status_code == 201, r.text
        out: dict[str, Any] = r.json()
        return out

    def claim(self, **kw: Any) -> Any:
        body: dict[str, Any] = {
            "text": "The company was sued.",
            "classification": "FACT",
            "material": True,
        }
        body.update(kw)
        return self.client.post(self.url("claims"), json=body, headers=self.h)


@pytest.fixture
def ctx(client: TestClient, db_app: FastAPI, tenant: str) -> Ctx:
    return Ctx(client, db_app, tenant, resolved_case(client, db_app, tenant))


def link(ev: dict[str, Any], relation: str = "SUPPORTS") -> dict[str, str]:
    return {"evidence_id": ev["id"], "relation": relation}


# --- evidence ---------------------------------------------------------------------------------


def test_web_evidence_keeps_access_separate_from_verification(ctx: Ctx) -> None:
    ev = ctx.evidence()
    assert ev["kind"] == "WEB" and ev["origin"] == "courts.example.org"
    assert ev["source_class_basis"] == "author_declared" and ev["accessed_at"]
    assert ev["freshness"] == "CURRENT" and "verification" not in ev
    got = ctx.client.get(ctx.url(f"evidence/{ev['id']}"), headers=ctx.h)
    assert got.status_code == 200 and got.json()["id"] == ev["id"]
    assert [e["id"] for e in ctx.client.get(ctx.url("evidence"), headers=ctx.h).json()] == [
        ev["id"]
    ]
    event = next(e for e in audit(ctx.app, ctx.tenant) if e.action == "evidence.added")
    assert set(event.details) == {"evidence_id"}


@pytest.mark.parametrize(
    "bad",
    [
        {"url": "http://insecure.example.org"},
        {"retrieved_at": None},
        {"source_class": None},
        {"document_id": str(uuid.uuid4())},
        {"connector_call_id": str(uuid.uuid4())},
        {"retrieved_at": (NOW + timedelta(days=2)).isoformat()},
        {"event_on": (NOW + timedelta(days=2)).date().isoformat()},
        {"content_hash": "xyz"},
        {"verification_status": "VERIFIED"},
        {"origin": " "},
    ],
    ids=[
        "http",
        "no-time",
        "no-class",
        "doc-id",
        "call-id",
        "future-read",
        "future-event",
        "hash",
        "status",
        "origin",
    ],
)
def test_invalid_evidence_is_refused(ctx: Ctx, bad: dict[str, Any]) -> None:
    body = {k: v for k, v in {**web(), **bad}.items() if v is not None}
    r = ctx.client.post(ctx.url("evidence"), json=body, headers=ctx.h)
    assert r.status_code == 422
    assert ctx.client.get(ctx.url("evidence"), headers=ctx.h).json() == []


def test_document_evidence_must_be_a_real_upload_of_this_case(ctx: Ctx) -> None:
    body = {
        "kind": "DOCUMENT",
        "evidence_type": "FINANCIAL",
        "title": "FY2025 accounts",
        "origin": "acme ltd",
        "excerpt": "Total current liabilities 4,100",
        "source_class": "COMMERCIAL",
        "document_id": str(uuid.uuid4()),
    }
    r = ctx.client.post(ctx.url("evidence"), json=body, headers=ctx.h)
    assert r.status_code == 422 and "not part of this case" in r.json()["error"]["message"]


def test_connector_evidence_needs_a_logged_successful_call(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    start(client, case_id, run_id, h)
    drain(executor(db_app, Fake(key, ["ok"]))[0])
    call = calls(client, case_id, run_id, h)[0]
    c = Ctx(client, db_app, tenant, case_id)
    body = {
        "kind": "CONNECTOR",
        "evidence_type": "REGISTRY",
        "title": "Registry record",
        "origin": "registry.example",
        "excerpt": "Active since 2010",
        "connector_call_id": call["id"],
    }
    r = client.post(c.url("evidence"), json=body, headers=h)
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["source_class_basis"] == "registry" and ev["source_class"] == "OFFICIAL"
    assert ev["provenance_ref"] == call["provenance_ref"] and ev["discovery_only"] is False
    assert ev["connector_call_id"] == call["id"]

    for extra in ({"source_class": "OFFICIAL"}, {"retrieved_at": NOW.isoformat()}):
        assert client.post(c.url("evidence"), json={**body, **extra}, headers=h).status_code == 422
    unknown = client.post(
        c.url("evidence"), json={**body, "connector_call_id": str(uuid.uuid4())}, headers=h
    )
    assert (
        unknown.status_code == 422 and "not part of this case" in unknown.json()["error"]["message"]
    )

    other_case = Ctx(client, db_app, tenant, resolved_case(client, db_app, tenant))
    foreign = client.post(other_case.url("evidence"), json=body, headers=h)
    assert foreign.status_code == 422  # a call of another case cannot back this case's evidence


def test_a_failed_call_cannot_be_evidence(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    start(client, case_id, run_id, h)
    drain(executor(db_app, Fake(key, ["permanent"]))[0])
    call = calls(client, case_id, run_id, h)[0]
    body = {
        "kind": "CONNECTOR",
        "evidence_type": "REGISTRY",
        "title": "x",
        "origin": "r",
        "excerpt": "x",
        "connector_call_id": call["id"],
    }
    r = client.post(f"/api/v1/cases/{case_id}/evidence", json=body, headers=h)
    assert r.status_code == 422 and "successful" in r.json()["error"]["message"]


def test_discovery_only_connector_evidence_is_flagged(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(
        client,
        db_app,
        tenant,
        {
            "key": key,
            "source_type": "news",
            "access_category": "DISCOVERY_ONLY",
            "source_class": "SECONDARY",
        },
    )
    start(client, case_id, run_id, h)
    drain(executor(db_app, Fake(key, ["ok"]))[0])
    call = next(c for c in calls(client, case_id, run_id, h))
    body = {
        "kind": "CONNECTOR",
        "evidence_type": "NEWS",
        "title": "Article",
        "origin": "news.example",
        "excerpt": "Reported a loss",
        "connector_call_id": call["id"],
    }
    ev = client.post(f"/api/v1/cases/{case_id}/evidence", json=body, headers=h).json()
    assert ev["discovery_only"] is True and ev["source_class"] == "SECONDARY"


# --- claims and computed verification ---------------------------------------------------------


def test_claim_without_evidence_is_unverified(ctx: Ctx) -> None:
    r = ctx.claim()
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["verification"]["status"] == "UNVERIFIED" and c["links"] == []
    assert c["freshness"] is None and "cannot be set" in c["notice"]


def test_status_cannot_be_sent_by_the_caller(ctx: Ctx) -> None:
    for field in ("verification_status", "verification", "status"):
        assert ctx.claim(**{field: "VERIFIED"}).status_code == 422


def test_one_official_source_verifies_and_freshness_is_reported(ctx: Ctx) -> None:
    ev = ctx.evidence()
    c = ctx.claim(evidence=[link(ev)]).json()
    assert c["verification"]["status"] == "VERIFIED" and c["freshness"] == "CURRENT"
    assert c["links"][0]["evidence"]["id"] == ev["id"]


def test_weak_evidence_alone_cannot_verify_a_material_claim(ctx: Ctx) -> None:
    ev = ctx.evidence(source_class="WEAK", is_primary=False)
    c = ctx.claim(evidence=[link(ev)]).json()
    assert c["verification"]["status"] == "PARTIALLY_VERIFIED"
    assert c["freshness"] is None  # only reliable evidence sets freshness


def test_material_adverse_needs_two_independent_sources_and_links_can_be_added(ctx: Ctx) -> None:
    first = ctx.evidence(is_primary=False, source_class="COMMERCIAL", origin="bureau.example")
    c = ctx.claim(adverse=True, evidence=[link(first)]).json()
    assert c["verification"]["status"] == "PARTIALLY_VERIFIED"
    assert "FR-3.7" in c["verification"]["needs"][0]

    same = ctx.evidence(is_primary=False, source_class="OFFICIAL", origin="bureau.example")
    r = ctx.client.post(ctx.url(f"claims/{c['id']}/evidence-links"), json=link(same), headers=ctx.h)
    assert r.json()["verification"]["status"] == "PARTIALLY_VERIFIED"  # same origin

    other = ctx.evidence(is_primary=False, source_class="OFFICIAL", origin="regulator.example")
    r = ctx.client.post(
        ctx.url(f"claims/{c['id']}/evidence-links"), json=link(other), headers=ctx.h
    )
    assert r.status_code == 201 and r.json()["verification"]["status"] == "VERIFIED"
    dup = ctx.client.post(
        ctx.url(f"claims/{c['id']}/evidence-links"), json=link(other), headers=ctx.h
    )
    assert dup.status_code == 409


def test_a_contradiction_flags_a_conflict_and_blocks_verified(ctx: Ctx) -> None:
    support = ctx.evidence()
    against = ctx.evidence(origin="other.example", title="Dismissal")
    c = ctx.claim(evidence=[link(support), link(against, "CONTRADICTS")]).json()
    assert c["verification"]["status"] == "PARTIALLY_VERIFIED" and c["verification"]["conflict"]


def test_source_unavailable_uses_a_real_unavailable_step(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, run_id, h = setup_run(client, db_app, tenant)  # empty registry: all steps unavailable
    run = client.get(f"/api/v1/cases/{case_id}/research-runs/{run_id}", headers=h).json()
    step = next(s for s in run["steps"] if s["category"] == "ADVERSE_SEARCH")
    c = Ctx(client, db_app, tenant, case_id)
    ok = c.claim(text="No adverse findings.", unavailable_step_id=step["id"])
    assert ok.status_code == 201 and ok.json()["verification"]["status"] == "SOURCE_UNAVAILABLE"
    bad = c.claim(unavailable_step_id=str(uuid.uuid4()))
    assert bad.status_code == 422


def test_a_planned_step_is_not_an_unavailable_source(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": f"k-{tenant}"})
    run = client.get(f"/api/v1/cases/{case_id}/research-runs/{run_id}", headers=h).json()
    planned = next(s for s in run["steps"] if s["state"] == "PLANNED")
    assert (
        Ctx(client, db_app, tenant, case_id).claim(unavailable_step_id=planned["id"]).status_code
        == 422
    )


def test_judgements_link_their_basis_and_are_not_applicable(ctx: Ctx) -> None:
    fact = ctx.claim(text="Current ratio is 0.7.").json()
    no_basis = ctx.claim(text="Liquidity is weak.", classification="INTERPRETATION")
    assert no_basis.status_code == 422 and "FR-3.8" in str(no_basis.json())
    ok = ctx.claim(
        text="Liquidity is weak.", classification="INTERPRETATION", basis_claim_ids=[fact["id"]]
    )
    assert ok.status_code == 201
    assert ok.json()["verification"]["status"] == "NOT_APPLICABLE"
    assert ok.json()["basis_claim_ids"] == [fact["id"]]
    assert ctx.claim(basis_claim_ids=[fact["id"]]).status_code == 422  # a fact has no basis claims
    foreign = ctx.claim(text="x", classification="INFERENCE", basis_claim_ids=[str(uuid.uuid4())])
    assert foreign.status_code == 422


def test_list_and_get_claims(ctx: Ctx) -> None:
    c = ctx.claim().json()
    assert [x["id"] for x in ctx.client.get(ctx.url("claims"), headers=ctx.h).json()] == [c["id"]]
    assert ctx.client.get(ctx.url(f"claims/{c['id']}"), headers=ctx.h).status_code == 200
    assert ctx.client.get(ctx.url(f"claims/{uuid.uuid4()}"), headers=ctx.h).status_code == 404


# --- isolation, permissions, immutability -----------------------------------------------------


def test_evidence_must_belong_to_the_same_case(ctx: Ctx) -> None:
    ev = ctx.evidence()
    other = Ctx(ctx.client, ctx.app, ctx.tenant, resolved_case(ctx.client, ctx.app, ctx.tenant))
    r = other.claim(evidence=[link(ev)])
    assert r.status_code == 422 and "not part of this case" in r.json()["error"]["message"]
    assert ctx.client.get(other.url(f"evidence/{ev['id']}"), headers=ctx.h).status_code == 404


def test_permissions_and_tenants(ctx: Ctx) -> None:
    ev = ctx.evidence()
    c = ctx.claim().json()
    for role in ("auditor", "administrator"):
        h = headers(ctx.app, role, ctx.tenant)
        assert ctx.client.post(ctx.url("evidence"), json=web(), headers=h).status_code == 403
        assert (
            ctx.client.post(
                ctx.url("claims"),
                json={"text": "x", "classification": "FACT", "material": True},
                headers=h,
            ).status_code
            == 403
        )
    assert (
        ctx.client.get(
            ctx.url("claims"), headers=headers(ctx.app, "auditor", ctx.tenant)
        ).status_code
        == 200
    )
    other = headers(ctx.app, "underwriter", ctx.tenant + "-x")
    for path in ("evidence", "claims", f"evidence/{ev['id']}", f"claims/{c['id']}"):
        assert ctx.client.get(ctx.url(path), headers=other).status_code == 404
    assert ctx.client.post(ctx.url("evidence"), json=web(), headers=other).status_code == 404


def test_audit_has_ids_only(ctx: Ctx) -> None:
    ev = ctx.evidence()
    c = ctx.claim(text="Secret allegation text", evidence=[link(ev)]).json()
    ctx.client.post(
        ctx.url(f"claims/{c['id']}/evidence-links"),
        json=link(ctx.evidence(origin="b.example"), "CONTRADICTS"),
        headers=ctx.h,
    )
    events = audit(ctx.app, ctx.tenant)
    assert {"claim.added", "claim.linked", "evidence.added"} <= {e.action for e in events}
    assert "Secret" not in str([e.details for e in events])


def test_everything_is_append_only_and_status_is_not_stored(ctx: Ctx) -> None:
    ev = ctx.evidence()
    ctx.claim(evidence=[link(ev)])
    engine = ctx.app.state.evidence_store._engine
    for table in ("evidence", "claims", "claim_basis", "claim_evidence"):
        for verb in ("UPDATE {} SET seq = seq", "DELETE FROM {}", "TRUNCATE {}"):
            sql = verb.format(table)  # noqa: S608 - fixed table names
            with pytest.raises(DBAPIError), engine.begin() as conn:
                conn.execute(sa.text(sql))
    columns = {c["name"] for c in sa.inspect(engine).get_columns("claims")}
    assert not {c for c in columns if "verif" in c or "status" in c}
