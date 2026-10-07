"""Entity candidates and the ambiguity stop against a real Postgres (AC-01, P-03, P-07)."""

import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from app.cases.entities import (
    ResearchBlockedError,
    require_research_allowed,
    research_readiness,
)
from app.cases.schemas import CaseStatus
from tests.test_cases_api import CASES, audit, headers, make_case


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def add(
    client: TestClient, db_app: FastAPI, tenant: str, case_id: str, name: str, **kw: Any
) -> Any:
    return client.post(
        f"{CASES}/{case_id}/entity-candidates",
        json={"legal_name": name, **kw},
        headers=headers(db_app, "underwriter", tenant),
    )


def case_state(client: TestClient, db_app: FastAPI, tenant: str, case_id: str) -> dict[str, Any]:
    data: dict[str, Any] = client.get(
        f"{CASES}/{case_id}", headers=headers(db_app, "reviewer", tenant)
    ).json()
    return data


def readiness(client: TestClient, db_app: FastAPI, tenant: str, case_id: str) -> dict[str, Any]:
    response = client.get(
        f"{CASES}/{case_id}/research-readiness", headers=headers(db_app, "reviewer", tenant)
    )
    assert response.status_code == 200
    data: dict[str, Any] = response.json()
    return data


# --- readiness logic (pure) ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "open_candidates", "allowed", "code"),
    [
        (CaseStatus.DRAFT, 0, False, "entity_not_identified"),
        (CaseStatus.DRAFT, 1, False, "entity_not_confirmed"),
        (CaseStatus.ENTITY_AMBIGUOUS, 2, False, "entity_ambiguous"),
        (CaseStatus.ENTITY_AMBIGUOUS, 5, False, "entity_ambiguous"),
        (CaseStatus.ENTITY_RESOLVED, 0, True, None),
    ],
)
def test_readiness_rules(
    status: CaseStatus, open_candidates: int, allowed: bool, code: str | None
) -> None:
    result = research_readiness(status, open_candidates)
    assert result.allowed is allowed
    assert [b.code for b in result.blockers] == ([code] if code else [])
    if code:
        assert result.blockers[0].message  # a plain-language explanation is always given


def test_the_server_side_gate_refuses_unresolved_cases() -> None:
    for status in (CaseStatus.DRAFT, CaseStatus.ENTITY_AMBIGUOUS):
        with pytest.raises(ResearchBlockedError):
            require_research_allowed(research_readiness(status, 2))
    require_research_allowed(research_readiness(CaseStatus.ENTITY_RESOLVED, 0))  # no error


# --- the ambiguity stop (AC-01) --------------------------------------------------------------


def test_new_case_cannot_research_and_says_why(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    result = readiness(client, db_app, tenant, case["id"])
    assert result["allowed"] is False
    assert result["blockers"][0]["code"] == "entity_not_identified"


def test_one_candidate_is_not_ambiguous_but_still_needs_confirmation(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    assert add(client, db_app, tenant, case["id"], "Acme Ltd").status_code == 201
    assert case_state(client, db_app, tenant, case["id"])["status"] == "DRAFT"
    result = readiness(client, db_app, tenant, case["id"])
    assert result["allowed"] is False
    assert result["blockers"][0]["code"] == "entity_not_confirmed"


def test_two_candidates_make_the_case_ambiguous_and_block_research(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    add(client, db_app, tenant, case["id"], "Acme Ltd", jurisdiction="Ontario")
    add(client, db_app, tenant, case["id"], "Acme Limited", jurisdiction="Alberta")
    assert case_state(client, db_app, tenant, case["id"])["status"] == "ENTITY_AMBIGUOUS"
    result = readiness(client, db_app, tenant, case["id"])
    assert result["allowed"] is False
    assert result["blockers"][0]["code"] == "entity_ambiguous"
    assert "2 legal entities" in result["blockers"][0]["message"]


def test_only_an_explicit_human_choice_resolves_it(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    first = add(client, db_app, tenant, case["id"], "Acme Ltd").json()
    second = add(client, db_app, tenant, case["id"], "Acme Limited").json()
    assert case_state(client, db_app, tenant, case["id"])["status"] == "ENTITY_AMBIGUOUS"

    response = client.post(
        f"{CASES}/{case['id']}/entity-resolution",
        json={"candidate_id": second["id"], "note": "Registry number matches"},
        headers=headers(db_app, "underwriter", tenant),
    )
    assert response.status_code == 200
    resolved = response.json()
    assert resolved["status"] == "ENTITY_RESOLVED"
    assert resolved["resolved_candidate_id"] == second["id"]
    assert resolved["resolved_by"] == "underwriter-1"
    assert readiness(client, db_app, tenant, case["id"])["allowed"] is True

    states = {
        c["id"]: c["state"]
        for c in client.get(
            f"{CASES}/{case['id']}/entity-candidates", headers=headers(db_app, "auditor", tenant)
        ).json()
    }
    assert states == {first["id"]: "rejected", second["id"]: "selected"}


def test_a_case_never_resolves_by_itself(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    """No path other than the resolve endpoint changes the status to resolved."""
    case = make_case(client, db_app, tenant)
    add(client, db_app, tenant, case["id"], "Only One Ltd")
    h = headers(db_app, "underwriter", tenant)
    forged = client.patch(
        f"{CASES}/{case['id']}",
        json={"expected_version": 1, "status": "ENTITY_RESOLVED"},
        headers=h,
    )
    assert forged.status_code == 422
    assert case_state(client, db_app, tenant, case["id"])["status"] == "DRAFT"


def test_cannot_resolve_with_a_foreign_or_unknown_candidate(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_a = make_case(client, db_app, tenant, legal_name="Case A")
    case_b = make_case(client, db_app, tenant, legal_name="Case B")
    cand_b = add(client, db_app, tenant, case_b["id"], "B Entity").json()
    h = headers(db_app, "underwriter", tenant)
    for candidate_id in (cand_b["id"], str(uuid.uuid4())):
        response = client.post(
            f"{CASES}/{case_a['id']}/entity-resolution",
            json={"candidate_id": candidate_id},
            headers=h,
        )
        assert response.status_code == 404
    assert case_state(client, db_app, tenant, case_a["id"])["status"] == "DRAFT"


def test_cannot_resolve_twice_or_add_candidates_after_resolution(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    cand = add(client, db_app, tenant, case["id"], "Acme Ltd").json()
    h = headers(db_app, "underwriter", tenant)
    url = f"{CASES}/{case['id']}/entity-resolution"
    assert client.post(url, json={"candidate_id": cand["id"]}, headers=h).status_code == 200
    again = client.post(url, json={"candidate_id": cand["id"]}, headers=h)
    assert again.status_code == 409 and again.json()["error"]["code"] == "conflict"
    late = add(client, db_app, tenant, case["id"], "Another Ltd")
    assert late.status_code == 409


# --- overrides (reopen) ----------------------------------------------------------------------


def test_reopen_needs_a_reason_and_restores_the_stop(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    add(client, db_app, tenant, case["id"], "Acme Ltd")
    chosen = add(client, db_app, tenant, case["id"], "Acme Limited").json()
    h = headers(db_app, "underwriter", tenant)
    client.post(
        f"{CASES}/{case['id']}/entity-resolution", json={"candidate_id": chosen["id"]}, headers=h
    )
    url = f"{CASES}/{case['id']}/entity-resolution/reopen"

    assert client.post(url, json={}, headers=h).status_code == 422
    assert client.post(url, json={"reason": "   "}, headers=h).status_code == 422
    reopened = client.post(url, json={"reason": "Wrong registry match"}, headers=h)
    assert reopened.status_code == 200
    body = reopened.json()
    assert body["status"] == "ENTITY_AMBIGUOUS"  # both candidates are open again
    assert body["resolved_candidate_id"] is None and body["resolved_by"] is None
    assert readiness(client, db_app, tenant, case["id"])["allowed"] is False
    assert client.post(url, json={"reason": "again"}, headers=h).status_code == 409


def test_resolved_entity_identity_cannot_be_edited_quietly(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    cand = add(client, db_app, tenant, case["id"], "Acme Ltd").json()
    h = headers(db_app, "underwriter", tenant)
    client.post(
        f"{CASES}/{case['id']}/entity-resolution", json={"candidate_id": cand["id"]}, headers=h
    )
    current = case_state(client, db_app, tenant, case["id"])
    url = f"{CASES}/{case['id']}"
    for field in ("legal_name", "registration_number", "jurisdiction"):
        blocked = client.patch(
            url, json={"expected_version": current["version"], field: "Changed"}, headers=h
        )
        assert blocked.status_code == 409, field
        assert "Reopen" in blocked.json()["error"]["message"]
    other = client.patch(
        url, json={"expected_version": current["version"], "terms": "Net 30"}, headers=h
    )
    assert other.status_code == 200  # non-identity edits are still fine


def test_resolution_history_is_kept_and_cannot_be_edited(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    cand = add(client, db_app, tenant, case["id"], "Acme Ltd").json()
    h = headers(db_app, "underwriter", tenant)
    client.post(
        f"{CASES}/{case['id']}/entity-resolution",
        json={"candidate_id": cand["id"], "note": "Matches registry"},
        headers=h,
    )
    client.post(
        f"{CASES}/{case['id']}/entity-resolution/reopen", json={"reason": "Check again"}, headers=h
    )
    log = db_app.state.entity_store.log_for_case(uuid.UUID(case["id"]), tenant)
    assert [(e["action"], e["actor"], e["note"]) for e in log] == [
        ("resolved", "underwriter-1", "Matches registry"),
        ("reopened", "underwriter-1", "Check again"),
    ]
    engine = db_app.state.entity_store._engine
    for statement in (
        "UPDATE entity_resolution_log SET note = 'edited'",
        "DELETE FROM entity_resolution_log",
        "TRUNCATE entity_resolution_log",
    ):
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
            conn.execute(sa.text(statement))


# --- candidate content rules -----------------------------------------------------------------


def test_candidate_lists_and_validation(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case = make_case(client, db_app, tenant)
    ok = add(
        client,
        db_app,
        tenant,
        case["id"],
        "Acme Ltd",
        aliases=["Acme", "  Acme Canada "],
        former_names=["Acme Industries"],
        subsidiaries=["Acme East"],
        parent_name="Acme Group",
        website="https://acme.example",
    )
    assert ok.status_code == 201
    body = ok.json()
    assert body["aliases"] == ["Acme", "Acme Canada"]
    assert body["source"] == "user_entered"  # the system never invents a candidate (P-02)
    assert "tenant_id" not in body

    bad_bodies = [
        {},
        {"legal_name": "   "},
        {"legal_name": "x" * 201},
        {"legal_name": "Ok", "aliases": ["a"] * 21},
        {"legal_name": "Ok", "aliases": [""]},
        {"legal_name": "Ok", "website": "javascript:alert(1)"},
        {"legal_name": "Ok", "state": "selected"},
        {"legal_name": "Ok", "source": "registry"},
        {"legal_name": "Ok", "tenant_id": "other"},
    ]
    for bad in bad_bodies:
        response = client.post(
            f"{CASES}/{case['id']}/entity-candidates",
            json=bad,
            headers=headers(db_app, "underwriter", tenant),
        )
        assert response.status_code == 422, bad


# --- permissions and tenant isolation (AC-10) ------------------------------------------------


@pytest.mark.parametrize("role", ["research_analyst", "auditor", "administrator", "service"])
def test_roles_without_case_write_cannot_add_resolve_or_reopen(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    case = make_case(client, db_app, tenant)
    cand = add(client, db_app, tenant, case["id"], "Acme Ltd").json()
    h = headers(db_app, role, tenant)
    base = f"{CASES}/{case['id']}"
    assert (
        client.post(f"{base}/entity-candidates", json={"legal_name": "X"}, headers=h).status_code
        == 403
    )
    assert (
        client.post(
            f"{base}/entity-resolution", json={"candidate_id": cand["id"]}, headers=h
        ).status_code
        == 403
    )
    assert (
        client.post(f"{base}/entity-resolution/reopen", json={"reason": "x"}, headers=h).status_code
        == 403
    )
    assert case_state(client, db_app, tenant, case["id"])["status"] == "DRAFT"


def test_another_tenant_is_refused_everywhere_and_audited(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    cand = add(client, db_app, tenant, case["id"], "Secret Entity Name Ltd").json()
    other = f"{tenant}-other"
    h = headers(db_app, "underwriter", other)
    base = f"{CASES}/{case['id']}"
    responses = [
        client.get(f"{base}/entity-candidates", headers=h),
        client.post(f"{base}/entity-candidates", json={"legal_name": "Evil"}, headers=h),
        client.post(f"{base}/entity-resolution", json={"candidate_id": cand["id"]}, headers=h),
        client.post(f"{base}/entity-resolution/reopen", json={"reason": "x"}, headers=h),
        client.get(f"{base}/research-readiness", headers=h),
    ]
    assert [r.status_code for r in responses] == [404] * 5
    events = audit(db_app, other)
    assert [e.action for e in events] == ["authz.cross_tenant_denied"] * 5
    assert "Secret Entity" not in " ".join(str(e) for e in events)
    assert case_state(client, db_app, tenant, case["id"])["status"] == "DRAFT"


def test_unknown_case_and_unauthenticated(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    h = headers(db_app, "underwriter", tenant)
    missing = f"{CASES}/{uuid.uuid4()}"
    assert client.get(f"{missing}/entity-candidates", headers=h).status_code == 404
    assert client.get(f"{missing}/research-readiness", headers=h).status_code == 404
    assert client.get(f"{missing}/research-readiness").status_code == 401
    assert client.post(f"{missing}/entity-resolution", json={}).status_code == 401


# --- audit (FR-1.7) --------------------------------------------------------------------------


def test_entity_actions_are_audited_without_names_or_reasons(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    add(client, db_app, tenant, case["id"], "Hidden Name Alpha Ltd")
    cand = add(client, db_app, tenant, case["id"], "Hidden Name Beta Ltd").json()
    h = headers(db_app, "underwriter", tenant)
    client.post(
        f"{CASES}/{case['id']}/entity-resolution",
        json={"candidate_id": cand["id"], "note": "private rationale text"},
        headers=h,
    )
    client.post(
        f"{CASES}/{case['id']}/entity-resolution/reopen",
        json={"reason": "private reopen reason"},
        headers=h,
    )
    events = list(reversed(audit(db_app, tenant)))
    actions = [e.action for e in events]
    assert actions == [
        "case.created",
        "entity.candidate_added",
        "entity.candidate_added",
        "entity.resolved",
        "entity.reopened",
    ]
    text = " ".join(str(e) for e in events)
    for secret in ("Hidden Name", "private rationale", "private reopen"):
        assert secret not in text


def test_store_refuses_actions_on_an_unknown_case(db_app: FastAPI, tenant: str) -> None:
    from app.cases.entity_store import CaseMissingError

    store = db_app.state.entity_store
    with pytest.raises(CaseMissingError):
        store.add_candidate(uuid.uuid4(), tenant, "u", {"legal_name": "X"})
