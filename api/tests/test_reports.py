"""Research reports: completion gates, immutable versions, wording rules (P-08, P-01, P-07)."""

import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from tests.test_cases_api import audit, headers, make_case
from tests.test_draft_recommendations import resolved_case
from tests.test_escalations import conflicted
from tests.test_evidence_api import Ctx, link
from tests.test_research_executor import Fake, calls, drain, executor, setup_run, start


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


@pytest.fixture
def ctx(client: TestClient, db_app: FastAPI, tenant: str) -> Ctx:
    return Ctx(client, db_app, tenant, resolved_case(client, db_app, tenant))


def preview(ctx: Ctx) -> dict[str, Any]:
    r = ctx.client.get(ctx.url("report-preview"), headers=ctx.h)
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


def complete(ctx: Ctx, note: str | None = None) -> Any:
    return ctx.client.post(ctx.url("reports"), json={"note": note} if note else {}, headers=ctx.h)


def gate(p: dict[str, Any], code: str) -> dict[str, Any]:
    return next(g for g in p["gates"] if g["code"] == code)


def verified_case(ctx: Ctx) -> dict[str, Any]:
    ev = ctx.evidence()
    claim: dict[str, Any] = ctx.claim(evidence=[link(ev)]).json()
    return claim


def test_empty_case_cannot_complete(ctx: Ctx) -> None:
    p = preview(ctx)
    assert p["can_complete"] is False and gate(p, "has_findings")["passed"] is False
    r = complete(ctx)
    assert r.status_code == 409 and "Nothing has been recorded" in r.json()["error"]["message"]
    blocked = [e for e in audit(ctx.app, ctx.tenant) if e.action == "report.blocked"]
    assert blocked and "has_findings" in blocked[0].details["failed_gates"]
    assert ctx.client.get(ctx.url("reports"), headers=ctx.h).json() == []


def test_preview_content_is_honest_about_what_was_not_done(ctx: Ctx) -> None:
    p = preview(ctx)
    c = p["content"]
    assert "not an underwriting decision" in c["notice"] and c["test_product"] is True
    assert c["adverse_search_statement"].startswith("An adverse search was not performed")
    assert c["evidence_confidence"]["level"] == "LOW"
    assert c["limitations"] == [
        "Payment behaviour was not assessed (data not used in this product)."
    ]
    assert c["counts"]["connector_sources_accessed"] == 0
    assert any("Registration number" in g for g in c["information_gaps"])
    assert (
        "As of" in c["final_statement"] and "not an underwriting decision" in c["final_statement"]
    )


def test_complete_stores_an_immutable_hashed_version(ctx: Ctx) -> None:
    claim = verified_case(ctx)
    p = preview(ctx)
    assert p["can_complete"] is True
    r = complete(ctx, "First pass")
    assert r.status_code == 201, r.text
    rep = r.json()
    assert (rep["version"], rep["immutable"], rep["integrity_verified"]) == (1, True, True)
    assert rep["note"] == "First pass" and len(rep["content_hash"]) == 64
    assert rep["content"]["counts"]["verified_material_findings"] == 1
    row = rep["content"]["material_findings"][0]
    assert row["claim_id"] == claim["id"] and row["verification_status"] == "VERIFIED"
    assert row["evidence_ids"]  # "show evidence" link
    assert rep["versions"]["evidence_rules"] == "1"
    event = next(e for e in audit(ctx.app, ctx.tenant) if e.action == "report.completed")
    assert set(event.details) == {"report_id", "version"}


def test_amendments_create_new_versions_and_history_is_kept(ctx: Ctx) -> None:
    verified_case(ctx)
    first = complete(ctx).json()
    ctx.claim(text="A second fact.", evidence=[link(ctx.evidence(origin="b.example"))])
    second = complete(ctx, "Amended").json()
    assert (first["version"], second["version"]) == (1, 2)
    history = ctx.client.get(ctx.url("reports"), headers=ctx.h).json()
    assert [h["version"] for h in history] == [2, 1] and "content" not in history[0]
    old = ctx.client.get(ctx.url("reports/1"), headers=ctx.h).json()
    assert old["content_hash"] == first["content_hash"] and old["integrity_verified"] is True
    assert old["content"]["counts"]["material_claims"] == 1  # version 1 still says what it said
    assert second["content"]["counts"]["material_claims"] == 2
    assert ctx.client.get(ctx.url("reports/9"), headers=ctx.h).status_code == 404


def test_open_escalation_blocks_completion_until_a_reviewer_resolves_it(ctx: Ctx) -> None:
    claim, support, _ = conflicted(ctx)
    assert gate(preview(ctx), "no_open_escalations")["passed"] is False
    assert complete(ctx).status_code == 409
    eid = ctx.client.get(ctx.url("escalations"), headers=ctx.h).json()["items"][0]["id"]
    ctx.client.post(
        ctx.url(f"escalations/{eid}/resolution"),
        json={
            "outcome": "SUPPORTING_PREVAILS",
            "explanation": "Primary record wins.",
            "preferred_evidence_id": support["id"],
        },
        headers=headers(ctx.app, "reviewer", ctx.tenant),
    )
    p = preview(ctx)
    assert p["can_complete"] is True
    assert p["content"]["conflicts"][0]["state"] == "RESOLVED"
    assert complete(ctx).status_code == 201 and claim["id"]


def test_a_material_claim_with_no_evidence_blocks_completion(ctx: Ctx) -> None:
    ctx.claim(text="Unsupported statement.")
    p = preview(ctx)
    assert gate(p, "material_claims_supported")["passed"] is False
    assert complete(ctx).status_code == 409
    # recorded as unverified, a claim with evidence of any kind is disclosed, not hidden
    ev = ctx.evidence(source_class="WEAK", is_primary=False)
    ctx.claim(text="Weakly supported.", evidence=[link(ev)])
    rows = preview(ctx)["content"]["unverified_claims"]
    assert {r["verification_status"] for r in rows} <= {"UNVERIFIED", "PARTIALLY_VERIFIED"}
    assert any(r["text"] == "Weakly supported." for r in rows)


def test_confidence_levels_follow_the_rules(ctx: Ctx) -> None:
    verified_case(ctx)
    high = preview(ctx)["content"]["evidence_confidence"]
    assert high["level"] == "HIGH" and high["rules_version"] == "1"
    weak = ctx.evidence(source_class="WEAK", is_primary=False, origin="blog.example")
    ctx.claim(text="Rumour of fraud.", adverse=True, evidence=[link(weak)])
    low = preview(ctx)["content"]["evidence_confidence"]
    assert low["level"] == "LOW" and any("adverse" in x for x in low["explanations"])


def test_moderate_when_a_material_claim_is_only_partly_verified(ctx: Ctx) -> None:
    verified_case(ctx)
    weak = ctx.evidence(source_class="WEAK", is_primary=False, origin="blog.example")
    ctx.claim(text="Probably growing.", evidence=[link(weak)])
    assert preview(ctx)["content"]["evidence_confidence"]["level"] == "MODERATE"


def test_negative_search_wording_needs_a_real_search(ctx: Ctx) -> None:
    news = ctx.evidence(
        evidence_type="NEWS",
        origin="news.example",
        source_class="SECONDARY",
        is_primary=False,
        title="Sector news",
    )
    ctx.claim(text="Sector is stable.", material=False, evidence=[link(news)])
    stmt = preview(ctx)["content"]["adverse_search_statement"]
    assert stmt.startswith("No adverse information was found in the sources searched: news.example")
    assert stmt.endswith("This does not mean that none exists.")
    ctx.claim(
        text="A lawsuit exists.",
        adverse=True,
        category="ADVERSE_SEARCH",
        evidence=[link(ctx.evidence(origin="c.example"))],
    )
    assert "1 adverse claim(s) were recorded" in preview(ctx)["content"]["adverse_search_statement"]


def test_verification_log_and_counts_come_from_real_calls(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    key = f"k-{tenant}"
    case_id, run_id, h = setup_run(client, db_app, tenant, {"key": key})
    c = Ctx(client, db_app, tenant, case_id)
    start(client, case_id, run_id, h)
    drain(executor(db_app, Fake(key, ["ok"]))[0])
    call = calls(client, case_id, run_id, h)[0]
    ev = client.post(
        c.url("evidence"),
        json={
            "kind": "CONNECTOR",
            "evidence_type": "REGISTRY",
            "title": "Record",
            "origin": "r.example",
            "excerpt": "Active",
            "connector_call_id": call["id"],
        },
        headers=h,
    ).json()
    client.post(
        c.url("claims"),
        json={
            "text": "Entity is active.",
            "classification": "FACT",
            "material": True,
            "evidence": [link(ev)],
        },
        headers=h,
    )
    content = preview(c)["content"]
    registry = next(r for r in content["verification_log"] if r["category"] == "ENTITY_REGISTRY")
    assert registry["accessed"] is True and registry["source_key"] == key
    others = [r for r in content["verification_log"] if r["category"] != "ENTITY_REGISTRY"]
    assert all(r["accessed"] is False and r["state"] == "NOT_AVAILABLE" for r in others)
    assert content["counts"]["connector_sources_accessed"] == 1
    assert content["counts"]["unavailable_sources"] == 3
    assert complete(c).json()["versions"]["connectors"] == {key: "test-1"}


def test_a_run_in_flight_blocks_completion(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, run_id, h = setup_run(client, db_app, tenant)
    c = Ctx(client, db_app, tenant, case_id)
    verified = c.evidence()
    c.claim(evidence=[link(verified)])
    start(client, case_id, run_id, h)
    p = preview(c)
    assert gate(p, "no_research_in_flight")["passed"] is False
    drain(executor(db_app)[0])
    assert gate(preview(c), "no_research_in_flight")["passed"] is True


def test_entity_must_be_resolved(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case = make_case(client, db_app, tenant)
    c = Ctx(client, db_app, tenant, case["id"])
    p = preview(c)
    assert gate(p, "entity_resolved")["passed"] is False
    assert complete(c).status_code == 409


def test_permissions_and_tenants(ctx: Ctx) -> None:
    verified_case(ctx)
    for role in ("research_analyst", "auditor", "administrator", "service"):
        assert (
            ctx.client.post(
                ctx.url("reports"), json={}, headers=headers(ctx.app, role, ctx.tenant)
            ).status_code
            == 403
        )
    complete(ctx)
    assert (
        ctx.client.get(
            ctx.url("reports/1"), headers=headers(ctx.app, "auditor", ctx.tenant)
        ).status_code
        == 200
    )
    assert (
        ctx.client.get(
            ctx.url("report-preview"), headers=headers(ctx.app, "auditor", ctx.tenant)
        ).status_code
        == 200
    )
    other = headers(ctx.app, "underwriter", ctx.tenant + "-x")
    for method, path in (("get", "report-preview"), ("get", "reports"), ("get", "reports/1")):
        assert getattr(ctx.client, method)(ctx.url(path), headers=other).status_code == 404
    assert ctx.client.post(ctx.url("reports"), json={}, headers=other).status_code == 404


def test_reports_cannot_be_edited_deleted_or_tampered_with(ctx: Ctx) -> None:
    verified_case(ctx)
    complete(ctx)
    engine = ctx.app.state.report_store._engine
    for verb in ("UPDATE {} SET note = 'x'", "DELETE FROM {}", "TRUNCATE {}"):
        sql = verb.format("report_versions")  # noqa: S608 - fixed table name
        with pytest.raises(DBAPIError), engine.begin() as conn:
            conn.execute(sa.text(sql))
    assert uuid.UUID(ctx.case_id)


def test_report_contract_has_no_score_rating_or_decision_fields() -> None:
    from scripts.export_openapi import build_spec
    from tests.p09 import offending_names

    assert offending_names(build_spec()) == []
