"""Escalations and conflict handling against a real Postgres (P-07)."""

import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from tests.test_cases_api import audit, headers
from tests.test_draft_recommendations import resolved_case
from tests.test_evidence_api import Ctx, link


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


@pytest.fixture
def ctx(client: TestClient, db_app: FastAPI, tenant: str) -> Ctx:
    return Ctx(client, db_app, tenant, resolved_case(client, db_app, tenant))


def reviewer(ctx: Ctx) -> dict[str, str]:
    return headers(ctx.app, "reviewer", ctx.tenant)


def conflicted(ctx: Ctx) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    support = ctx.evidence()
    against = ctx.evidence(origin="other.example", title="Dismissal")
    claim = ctx.claim(evidence=[link(support), link(against, "CONTRADICTS")]).json()
    return claim, support, against


def escalations(ctx: Ctx) -> dict[str, Any]:
    out: dict[str, Any] = ctx.client.get(ctx.url("escalations"), headers=ctx.h).json()
    return out


def test_a_reliable_contradiction_on_a_material_claim_raises_a_review_automatically(
    ctx: Ctx,
) -> None:
    claim, _, _ = conflicted(ctx)
    listing = escalations(ctx)
    assert listing["open_count"] == 1
    e = listing["items"][0]
    assert (e["kind"], e["state"], e["label"]) == ("CONFLICT", "OPEN", "HUMAN_REVIEW_REQUIRED")
    assert e["claim_id"] == claim["id"] and e["raised_by_system"] is True
    sides = {r["side"] for r in e["comparison"]}
    assert sides == {"SUPPORTS", "CONTRADICTS"}
    row = e["comparison"][0]
    assert {"authority", "date", "freshness", "specificity", "data_quality"} <= set(row)
    assert row["independent_of_other_side"] is True
    assert claim["verification"]["conflict"] is True


def test_no_escalation_for_non_material_claims_or_weak_contradictions(ctx: Ctx) -> None:
    support, against = ctx.evidence(), ctx.evidence(origin="o.example")
    ctx.claim(material=False, evidence=[link(support), link(against, "CONTRADICTS")])
    weak = ctx.evidence(origin="w.example", source_class="WEAK", is_primary=False)
    ctx.claim(text="Another", evidence=[link(support), link(weak, "CONTRADICTS")])
    assert escalations(ctx)["open_count"] == 0


def test_adding_a_contradiction_later_raises_it_once(ctx: Ctx) -> None:
    support = ctx.evidence()
    claim = ctx.claim(evidence=[link(support)]).json()
    assert escalations(ctx)["open_count"] == 0
    for origin in ("a.example", "b.example"):
        against = ctx.evidence(origin=origin)
        ctx.client.post(
            ctx.url(f"claims/{claim['id']}/evidence-links"),
            json=link(against, "CONTRADICTS"),
            headers=ctx.h,
        )
    assert escalations(ctx)["open_count"] == 1  # not raised twice
    event = [e for e in audit(ctx.app, ctx.tenant) if e.action == "escalation.raised"]
    assert len(event) == 1 and set(event[0].details) == {"escalation_id"}


def test_only_a_reviewer_can_resolve_and_nothing_resolves_it_automatically(ctx: Ctx) -> None:
    claim, support, _ = conflicted(ctx)
    eid = escalations(ctx)["items"][0]["id"]
    body = {
        "outcome": "SUPPORTING_PREVAILS",
        "explanation": "The registry record is the primary source.",
        "preferred_evidence_id": support["id"],
    }
    url = ctx.url(f"escalations/{eid}/resolution")
    for role in ("underwriter", "research_analyst", "auditor", "administrator", "service"):
        assert (
            ctx.client.post(url, json=body, headers=headers(ctx.app, role, ctx.tenant)).status_code
            == 403
        )
    assert escalations(ctx)["open_count"] == 1
    again = ctx.client.get(ctx.url(f"claims/{claim['id']}"), headers=ctx.h).json()
    assert again["verification"]["status"] == "PARTIALLY_VERIFIED"  # still blocked


def test_resolving_for_the_supporting_side_lets_the_claim_verify(ctx: Ctx) -> None:
    claim, support, against = conflicted(ctx)
    eid = escalations(ctx)["items"][0]["id"]
    r = ctx.client.post(
        ctx.url(f"escalations/{eid}/resolution"),
        json={
            "outcome": "SUPPORTING_PREVAILS",
            "explanation": "The registry record is the primary source.",
            "preferred_evidence_id": support["id"],
        },
        headers=reviewer(ctx),
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["state"] == "RESOLVED" and out["resolution"]["resolved_by"] == "reviewer-1"
    assert escalations(ctx)["open_count"] == 0
    now = ctx.client.get(ctx.url(f"claims/{claim['id']}"), headers=ctx.h).json()
    assert now["verification"]["status"] == "VERIFIED" and now["verification"]["conflict"] is False
    assert any("resolved the conflict" in r for r in now["verification"]["reasons"])
    assert against["id"] in [x["evidence"]["id"] for x in now["links"]]  # nothing was removed


def test_resolving_for_the_contradicting_side_leaves_the_claim_unverified(ctx: Ctx) -> None:
    claim, _, against = conflicted(ctx)
    eid = escalations(ctx)["items"][0]["id"]
    r = ctx.client.post(
        ctx.url(f"escalations/{eid}/resolution"),
        json={
            "outcome": "CONTRADICTING_PREVAILS",
            "explanation": "The dismissal is later and more specific.",
            "preferred_evidence_id": against["id"],
        },
        headers=reviewer(ctx),
    )
    assert r.status_code == 200
    now = ctx.client.get(ctx.url(f"claims/{claim['id']}"), headers=ctx.h).json()
    assert now["verification"]["status"] == "UNVERIFIED"


def test_a_new_contradiction_after_resolution_reopens_the_question(ctx: Ctx) -> None:
    claim, support, _ = conflicted(ctx)
    eid = escalations(ctx)["items"][0]["id"]
    ctx.client.post(
        ctx.url(f"escalations/{eid}/resolution"),
        json={
            "outcome": "SUPPORTING_PREVAILS",
            "explanation": "Primary record wins.",
            "preferred_evidence_id": support["id"],
        },
        headers=reviewer(ctx),
    )
    newer = ctx.evidence(origin="third.example", title="Appeal notice")
    r = ctx.client.post(
        ctx.url(f"claims/{claim['id']}/evidence-links"),
        json=link(newer, "CONTRADICTS"),
        headers=ctx.h,
    )
    assert r.json()["verification"]["status"] == "PARTIALLY_VERIFIED"
    assert r.json()["verification"]["conflict"] is True
    listing = escalations(ctx)
    assert listing["open_count"] == 1 and len(listing["items"]) == 2


def test_resolution_rules(ctx: Ctx) -> None:
    claim, support, against = conflicted(ctx)
    eid = escalations(ctx)["items"][0]["id"]
    url = ctx.url(f"escalations/{eid}/resolution")
    h = reviewer(ctx)
    bad_bodies = [
        {"outcome": "NO_CLAIM_CHANGE", "explanation": "Looks fine to me, moving on."},
        {"outcome": "SUPPORTING_PREVAILS", "explanation": "Primary record wins."},
        {
            "outcome": "SUPPORTING_PREVAILS",
            "explanation": "short",
            "preferred_evidence_id": support["id"],
        },
        {
            "outcome": "SUPPORTING_PREVAILS",
            "explanation": "Primary record wins.",
            "preferred_evidence_id": against["id"],
        },  # wrong side
        {
            "outcome": "SUPPORTING_PREVAILS",
            "explanation": "Primary record wins.",
            "preferred_evidence_id": str(uuid.uuid4()),
        },
    ]
    for bad in bad_bodies:
        assert ctx.client.post(url, json=bad, headers=h).status_code == 422, bad
    assert escalations(ctx)["open_count"] == 1
    good = {
        "outcome": "SUPPORTING_PREVAILS",
        "explanation": "Primary record wins.",
        "preferred_evidence_id": support["id"],
    }
    assert ctx.client.post(url, json=good, headers=h).status_code == 200
    assert ctx.client.post(url, json=good, headers=h).status_code == 409
    assert claim["id"]


def test_people_can_raise_other_escalations_and_a_reviewer_closes_them(ctx: Ctx) -> None:
    r = ctx.client.post(
        ctx.url("escalations"),
        json={"kind": "MATERIAL_AMBIGUITY", "description": "Two subsidiaries share the name."},
        headers=ctx.h,
    )
    assert r.status_code == 201 and r.json()["raised_by_system"] is False
    eid = r.json()["id"]
    url = ctx.url(f"escalations/{eid}/resolution")
    wrong = {
        "outcome": "SUPPORTING_PREVAILS",
        "explanation": "Not allowed here.",
        "preferred_evidence_id": str(uuid.uuid4()),
    }
    assert ctx.client.post(url, json=wrong, headers=reviewer(ctx)).status_code == 422
    done = ctx.client.post(
        url,
        json={"outcome": "NO_CLAIM_CHANGE", "explanation": "Confirmed the right subsidiary."},
        headers=reviewer(ctx),
    )
    assert done.status_code == 200 and done.json()["state"] == "RESOLVED"
    assert (
        ctx.client.post(
            ctx.url("escalations"), json={"kind": "CONFLICT", "description": "x"}, headers=ctx.h
        ).status_code
        == 422
    )  # conflicts are raised by the system only
    assert (
        ctx.client.post(
            ctx.url("escalations"),
            json={"kind": "OTHER", "description": "x", "claim_id": str(uuid.uuid4())},
            headers=ctx.h,
        ).status_code
        == 422
    )


def test_permissions_tenants_and_audit(ctx: Ctx) -> None:
    claim, support, _ = conflicted(ctx)
    eid = escalations(ctx)["items"][0]["id"]
    other = headers(ctx.app, "reviewer", ctx.tenant + "-x")
    assert ctx.client.get(ctx.url("escalations"), headers=other).status_code == 404
    assert ctx.client.get(ctx.url(f"escalations/{eid}"), headers=other).status_code == 404
    assert (
        ctx.client.post(
            ctx.url(f"escalations/{eid}/resolution"),
            json={
                "outcome": "SUPPORTING_PREVAILS",
                "explanation": "Primary record wins.",
                "preferred_evidence_id": support["id"],
            },
            headers=other,
        ).status_code
        == 404
    )
    assert (
        ctx.client.get(
            ctx.url("escalations"), headers=headers(ctx.app, "auditor", ctx.tenant)
        ).status_code
        == 200
    )
    ctx.client.post(
        ctx.url(f"escalations/{eid}/resolution"),
        json={
            "outcome": "SUPPORTING_PREVAILS",
            "explanation": "Primary record wins.",
            "preferred_evidence_id": support["id"],
        },
        headers=reviewer(ctx),
    )
    event = next(e for e in audit(ctx.app, ctx.tenant) if e.action == "escalation.resolved")
    assert event.details == {"escalation_id": eid, "outcome": "SUPPORTING_PREVAILS"}
    assert "Primary record" not in str(event.details) and claim["id"]


def test_escalations_are_append_only(ctx: Ctx) -> None:
    conflicted(ctx)
    engine = ctx.app.state.escalation_store._engine
    for table in ("escalations", "escalation_resolutions"):
        for verb in ("UPDATE {} SET seq = seq", "DELETE FROM {}", "TRUNCATE {}"):
            sql = verb.format(table)  # noqa: S608 - fixed table names
            with pytest.raises(DBAPIError), engine.begin() as conn:
                conn.execute(sa.text(sql))
