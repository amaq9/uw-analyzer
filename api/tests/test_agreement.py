"""Agreement view against a real Postgres: counts how recorded outcomes compare with drafts."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.test_cases_api import headers
from tests.test_draft_recommendations import payload, post_draft, resolved_case
from tests.test_underwriter_decision import decide

AGREEMENT = "/api/v1/agreement"


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def make(client: TestClient, app: FastAPI, tenant: str, body: dict[str, object]) -> None:
    case_id = resolved_case(client, app, tenant)
    draft_id = post_draft(client, app, tenant, case_id, payload("900000")).json()["id"]
    assert decide(client, app, tenant, case_id, draft_id, body).status_code == 201


def test_empty_report(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    r = client.get(AGREEMENT, headers=headers(db_app, "underwriter", tenant))
    assert r.status_code == 200
    assert r.json()["totals"]["decided"] == 0 and r.json()["rows"] == []
    assert r.json()["test_product"] is True


def test_totals_and_rows(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    make(client, db_app, tenant, {"action": "ADOPT"})
    make(
        client,
        db_app,
        tenant,
        {
            "action": "CHANGE",
            "reason": "Lower",
            "final_outcome": "APPROVE",
            "final_amount": "500000",
        },
    )
    make(client, db_app, tenant, {"action": "CHANGE", "reason": "No", "final_outcome": "DECLINE"})
    make(client, db_app, tenant, {"action": "REJECT", "reason": "Redo"})
    body = client.get(AGREEMENT, headers=headers(db_app, "auditor", tenant)).json()
    assert body["totals"] == {
        "decided": 4,
        "adopted": 1,
        "changed": 2,
        "rejected": 1,
        "same_outcome": 2,
        "different_outcome": 1,
        "amount_differs_same_outcome": 1,
    }
    assert len(body["rows"]) == 4
    newest = body["rows"][0]
    assert newest["action"] == "REJECT" and newest["final_outcome"] is None
    assert newest["same_outcome"] is False and newest["reason"] == "Redo"
    assert (
        len(
            client.get(AGREEMENT + "?limit=2", headers=headers(db_app, "auditor", tenant)).json()[
                "rows"
            ]
        )
        == 2
    )


def test_tenant_scoped_and_permission_checked(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    make(client, db_app, tenant, {"action": "ADOPT"})
    other = client.get(AGREEMENT, headers=headers(db_app, "underwriter", tenant + "-x")).json()
    assert other["totals"]["decided"] == 0
    assert (
        client.get(AGREEMENT, headers=headers(db_app, "administrator", tenant)).status_code == 403
    )
    assert client.get(AGREEMENT).status_code == 401
