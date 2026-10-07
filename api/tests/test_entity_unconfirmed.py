"""A person can record that the legal entity could not be confirmed or found (recommendation policy
2e2, item 5). Research never runs for such a case, and only a person can reopen it."""

import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from app.cases.entities import research_readiness
from app.cases.schemas import CaseStatus
from tests.test_cases_api import CASES, audit, headers, make_case


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def unconfirm(
    client: TestClient,
    app: FastAPI,
    tenant: str,
    case_id: str,
    reason: Any = "No registry match",
    role: str = "underwriter",
) -> Any:
    return client.post(
        f"{CASES}/{case_id}/entity-resolution/unconfirmed",
        json={"reason": reason},
        headers=headers(app, role, tenant),
    )


def state(client: TestClient, app: FastAPI, tenant: str, case_id: str) -> dict[str, Any]:
    data: dict[str, Any] = client.get(
        f"{CASES}/{case_id}", headers=headers(app, "reviewer", tenant)
    ).json()
    return data


def test_readiness_wording_never_reads_as_a_decision() -> None:
    result = research_readiness(CaseStatus.ENTITY_UNCONFIRMED, 0)
    assert result.allowed is False
    assert result.blockers[0].code == "entity_unconfirmed"
    text = result.blockers[0].message.lower()
    assert "decline" not in text and "approve" not in text and "reject" not in text


def test_a_person_can_record_it_from_a_new_case_and_research_stays_blocked(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    response = unconfirm(client, db_app, tenant, case["id"])
    assert response.status_code == 200
    assert response.json()["status"] == "ENTITY_UNCONFIRMED"
    ready = client.get(
        f"{CASES}/{case['id']}/research-readiness", headers=headers(db_app, "reviewer", tenant)
    ).json()
    assert ready["allowed"] is False and ready["blockers"][0]["code"] == "entity_unconfirmed"


def test_it_can_also_be_recorded_from_an_ambiguous_case(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    for name in ("Acme Ltd", "Acme Limited"):
        client.post(
            f"{CASES}/{case['id']}/entity-candidates",
            json={"legal_name": name},
            headers=headers(db_app, "underwriter", tenant),
        )
    assert state(client, db_app, tenant, case["id"])["status"] == "ENTITY_AMBIGUOUS"
    assert unconfirm(client, db_app, tenant, case["id"]).status_code == 200
    assert state(client, db_app, tenant, case["id"])["status"] == "ENTITY_UNCONFIRMED"


def test_a_reason_is_mandatory(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case = make_case(client, db_app, tenant)
    for bad in ("", "   ", None):
        assert unconfirm(client, db_app, tenant, case["id"], bad).status_code == 422
    assert state(client, db_app, tenant, case["id"])["status"] == "DRAFT"


def test_it_cannot_be_recorded_twice_or_over_a_resolved_entity(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    assert unconfirm(client, db_app, tenant, case["id"]).status_code == 200
    again = unconfirm(client, db_app, tenant, case["id"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "conflict"

    resolved = make_case(client, db_app, tenant, legal_name="Resolved Ltd")
    cand = client.post(
        f"{CASES}/{resolved['id']}/entity-candidates",
        json={"legal_name": "Resolved Ltd"},
        headers=headers(db_app, "underwriter", tenant),
    ).json()
    client.post(
        f"{CASES}/{resolved['id']}/entity-resolution",
        json={"candidate_id": cand["id"]},
        headers=headers(db_app, "underwriter", tenant),
    )
    assert unconfirm(client, db_app, tenant, resolved["id"]).status_code == 409


def test_candidates_and_choices_are_blocked_until_a_person_reopens(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    cand = client.post(
        f"{CASES}/{case['id']}/entity-candidates",
        json={"legal_name": "Acme Ltd"},
        headers=headers(db_app, "underwriter", tenant),
    ).json()
    unconfirm(client, db_app, tenant, case["id"])
    h = headers(db_app, "underwriter", tenant)
    late = client.post(
        f"{CASES}/{case['id']}/entity-candidates", json={"legal_name": "X"}, headers=h
    )
    choose = client.post(
        f"{CASES}/{case['id']}/entity-resolution", json={"candidate_id": cand["id"]}, headers=h
    )
    assert late.status_code == 409 and choose.status_code == 409

    reopened = client.post(
        f"{CASES}/{case['id']}/entity-resolution/reopen",
        json={"reason": "Found the registry"},
        headers=h,
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "DRAFT"  # one open candidate: not ambiguous
    assert (
        client.post(
            f"{CASES}/{case['id']}/entity-candidates", json={"legal_name": "Y"}, headers=h
        ).status_code
        == 201
    )


def test_it_is_logged_permanently_and_audited_without_the_reason(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    unconfirm(client, db_app, tenant, case["id"], "private reason text")
    log = db_app.state.entity_store.log_for_case(uuid.UUID(case["id"]), tenant)
    assert [(e["action"], e["note"]) for e in log] == [("unconfirmed", "private reason text")]
    events = audit(db_app, tenant)
    assert [e.action for e in events][0] == "entity.unconfirmed"
    assert "private reason" not in str(events)
    engine = db_app.state.entity_store._engine
    for statement in (
        "UPDATE entity_resolution_log SET note = 'edited'",
        "DELETE FROM entity_resolution_log",
    ):
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
            conn.execute(sa.text(statement))


@pytest.mark.parametrize("role", ["research_analyst", "auditor", "administrator", "service"])
def test_only_case_writers_can_record_it(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    case = make_case(client, db_app, tenant)
    assert unconfirm(client, db_app, tenant, case["id"], role=role).status_code == 403
    assert state(client, db_app, tenant, case["id"])["status"] == "DRAFT"


def test_another_tenant_cannot_record_it(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case = make_case(client, db_app, tenant)
    other = f"{tenant}-other"
    assert unconfirm(client, db_app, other, case["id"]).status_code == 404
    assert state(client, db_app, tenant, case["id"])["status"] == "DRAFT"
    assert [e.action for e in audit(db_app, other)] == ["authz.cross_tenant_denied"]
