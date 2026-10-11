"""Underwriter decision on a draft (ADR 0005 items 7 and 8) against a real Postgres."""

from decimal import Decimal
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from tests.test_cases_api import CASES, audit, headers
from tests.test_draft_recommendations import payload, post_draft, resolved_case


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def decide(
    client: TestClient,
    app: FastAPI,
    tenant: str,
    case_id: str,
    draft_id: str,
    body: dict[str, Any],
    role: str = "underwriter",
) -> Any:
    return client.post(
        f"{CASES}/{case_id}/draft-recommendations/{draft_id}/decision",
        json=body,
        headers=headers(app, role, tenant),
    )


def draft(client: TestClient, app: FastAPI, tenant: str, ai: str = "900000") -> tuple[str, str]:
    case_id = resolved_case(client, app, tenant)
    response = post_draft(client, app, tenant, case_id, payload(ai))
    assert response.status_code == 201, response.text
    return case_id, response.json()["id"]


def test_adopt_keeps_the_draft_outcome_and_amount(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, draft_id = draft(client, db_app, tenant)
    r = decide(client, db_app, tenant, case_id, draft_id, {"action": "ADOPT"})
    assert r.status_code == 201, r.text
    d = r.json()
    assert (d["final_outcome"], d["agrees"], d["decided_by"]) == ("APPROVE", True, "underwriter-1")
    assert Decimal(d["final_amount"]) == Decimal("1000000") and d["currency"] == "CAD"
    assert "named person" in d["notice"]
    got = client.get(
        f"{CASES}/{case_id}/draft-recommendations/{draft_id}/decision",
        headers=headers(db_app, "auditor", tenant),
    )
    assert got.status_code == 200 and got.json()["id"] == d["id"]


def test_change_needs_a_reason_and_an_outcome(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, draft_id = draft(client, db_app, tenant)
    for bad in (
        {"action": "CHANGE", "final_outcome": "DECLINE"},
        {"action": "CHANGE", "reason": "x"},
        {"action": "CHANGE", "reason": "x", "final_outcome": "APPROVE"},
        {"action": "CHANGE", "reason": "x", "final_outcome": "DECLINE", "final_amount": "5"},
        {"action": "ADOPT", "final_outcome": "DECLINE"},
        {"action": "REJECT"},
        {"action": "REJECT", "reason": "x", "final_outcome": "DECLINE"},
        {"action": "CHANGE", "reason": "x", "final_outcome": "APPROVE", "final_amount": "0"},
    ):
        r = decide(client, db_app, tenant, case_id, draft_id, bad)
        assert r.status_code == 422, bad


def test_change_to_a_lower_amount_or_to_decline_is_recorded_as_disagreement(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, draft_id = draft(client, db_app, tenant)
    r = decide(
        client,
        db_app,
        tenant,
        case_id,
        draft_id,
        {
            "action": "CHANGE",
            "reason": "Concentration worries me.",
            "final_outcome": "APPROVE",
            "final_amount": "600000",
        },
    )
    d = r.json()
    assert (d["agrees"], d["action"]) == (False, "CHANGE")
    assert Decimal(d["final_amount"]) == Decimal("600000")

    case2, draft2 = draft(client, db_app, tenant)
    r2 = decide(
        client,
        db_app,
        tenant,
        case2,
        draft2,
        {"action": "CHANGE", "reason": "Too risky.", "final_outcome": "DECLINE"},
    )
    assert r2.json()["final_outcome"] == "DECLINE" and r2.json()["final_amount"] is None


def test_change_cannot_exceed_the_request_or_match_the_draft(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, draft_id = draft(client, db_app, tenant)
    over = decide(
        client,
        db_app,
        tenant,
        case_id,
        draft_id,
        {
            "action": "CHANGE",
            "reason": "x",
            "final_outcome": "APPROVE",
            "final_amount": "1000000.01",
        },
    )
    assert over.status_code == 422
    same = decide(
        client,
        db_app,
        tenant,
        case_id,
        draft_id,
        {"action": "CHANGE", "reason": "x", "final_outcome": "APPROVE", "final_amount": "1000000"},
    )
    assert same.status_code == 422 and "adopt" in same.json()["error"]["message"]


def test_reject_records_no_outcome(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case_id, draft_id = draft(client, db_app, tenant)
    r = decide(
        client, db_app, tenant, case_id, draft_id, {"action": "REJECT", "reason": "Wrong entity."}
    )
    d = r.json()
    assert r.status_code == 201
    assert (d["final_outcome"], d["final_amount"], d["agrees"]) == (None, None, False)


def test_one_decision_per_draft_and_only_for_the_newest_draft(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, first = draft(client, db_app, tenant)
    assert decide(client, db_app, tenant, case_id, first, {"action": "ADOPT"}).status_code == 201
    again = decide(client, db_app, tenant, case_id, first, {"action": "ADOPT"})
    assert again.status_code == 409
    second = post_draft(client, db_app, tenant, case_id, payload("850000")).json()["id"]
    assert decide(client, db_app, tenant, case_id, first, {"action": "ADOPT"}).status_code == 409
    assert decide(client, db_app, tenant, case_id, second, {"action": "ADOPT"}).status_code == 201


def test_only_roles_with_decision_record_can_decide(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, draft_id = draft(client, db_app, tenant)
    for role in ("research_analyst", "auditor", "administrator", "service"):
        r = decide(client, db_app, tenant, case_id, draft_id, {"action": "ADOPT"}, role)
        assert r.status_code == 403, role
    assert (
        decide(
            client, db_app, tenant, case_id, draft_id, {"action": "ADOPT"}, "reviewer"
        ).status_code
        == 201
    )


def test_no_decision_yet_is_404_and_other_tenants_see_nothing(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, draft_id = draft(client, db_app, tenant)
    url = f"{CASES}/{case_id}/draft-recommendations/{draft_id}/decision"
    assert client.get(url, headers=headers(db_app, "underwriter", tenant)).status_code == 404
    other = headers(db_app, "underwriter", tenant + "-x")
    assert client.get(url, headers=other).status_code == 404
    assert client.post(url, json={"action": "ADOPT"}, headers=other).status_code == 404


def test_audit_has_ids_and_action_but_no_content(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, draft_id = draft(client, db_app, tenant)
    decide(
        client,
        db_app,
        tenant,
        case_id,
        draft_id,
        {"action": "REJECT", "reason": "Secret reasoning words"},
    )
    event = next(e for e in audit(db_app, tenant) if e.action == "decision.recorded")
    assert set(event.details) == {"decision_id", "draft_id", "action"}
    assert "Secret" not in str(event.details)


def test_decisions_cannot_be_edited_or_deleted(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id, draft_id = draft(client, db_app, tenant)
    decide(client, db_app, tenant, case_id, draft_id, {"action": "ADOPT"})
    engine = db_app.state.decision_store._engine  # noqa: SLF001
    for sql in (
        "UPDATE underwriter_decisions SET reason = 'x' WHERE draft_id = :d",
        "DELETE FROM underwriter_decisions WHERE draft_id = :d",
    ):
        with pytest.raises(DBAPIError), engine.begin() as conn:
            conn.execute(sa.text(sql), {"d": draft_id})
