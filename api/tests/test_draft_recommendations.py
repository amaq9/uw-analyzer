"""Draft recommendations (assisted mode, ADR 0008) against a real Postgres: the server applies the
approved policy, validates evidence, enforces permissions and tenants, and keeps drafts immutable."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from tests.test_cases_api import CASES, audit, headers, make_case

NOTICE = "Draft recommendation for the underwriter. Not a decision."
WEB = {
    "kind": "web",
    "url": "https://registry.example.org/filing/123",
    "retrieved_at": "2026-10-07T12:00:00Z",
    "quote": "Total current liabilities 4,100",
}
SOURCE = {
    "kind": "claude_code_session",
    "model": "claude-sonnet-5-5 via Claude Code",
    "skill_version": "financial-statement-assessment adapted 2026-10-07",
    "policy_version": "1.0",
}


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def resolved_case(
    client: TestClient,
    app: FastAPI,
    tenant: str,
    exposure: str | None = "1000000",
    currency: str = "CAD",
) -> str:
    extra: dict[str, Any] = {}
    if exposure is not None:
        extra = {"exposure_amount": exposure, "exposure_currency": currency}
    case = make_case(client, app, tenant, **extra)
    h = headers(app, "underwriter", tenant)
    cand = client.post(
        f"{CASES}/{case['id']}/entity-candidates", json={"legal_name": "Acme Ltd"}, headers=h
    ).json()
    done = client.post(
        f"{CASES}/{case['id']}/entity-resolution", json={"candidate_id": cand["id"]}, headers=h
    )
    assert done.status_code == 200
    return str(case["id"])


def payload(ai: str | None = "900000", **kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ai_proposed_amount": ai,
        "financial_findings_weak": False,
        "factors": [],
        "summary": "Liquidity and gearing look acceptable.",
        "reasons": [{"text": "Current ratio is 1.6x.", "evidence": [WEB]}],
        "information_gaps": ["Receivables aging not disclosed"],
        "source": SOURCE,
    }
    body.update(kw)
    return body


def post_draft(
    client: TestClient,
    app: FastAPI,
    tenant: str,
    case_id: str,
    body: dict[str, Any],
    role: str = "underwriter",
) -> Any:
    return client.post(
        f"{CASES}/{case_id}/draft-recommendations", json=body, headers=headers(app, role, tenant)
    )


# --- the policy is applied by the server -----------------------------------------------------


def test_80_percent_or_more_is_recommended_as_the_full_requested_amount(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    response = post_draft(client, db_app, tenant, case_id, payload("850000"))
    assert response.status_code == 201, response.text
    draft = response.json()
    assert (draft["outcome"], draft["band"]) == ("APPROVE", "FULL")
    assert Decimal(draft["recommended_amount"]) == Decimal("1000000")  # the request, not 850,000
    assert Decimal(draft["ai_proposed_amount"]) == Decimal("850000")  # the AI's figure is kept
    assert draft["requested_currency"] == "CAD" and draft["version"] == 1
    assert draft["rule_codes"] == []


def test_reduced_amount_is_rounded_down_and_needs_a_factor(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    factors = [{"code": "sector_outlook", "explanation": "Weak outlook for the sector."}]
    ok = post_draft(client, db_app, tenant, case_id, payload("637420", factors=factors))
    assert ok.status_code == 201
    draft = ok.json()
    assert (draft["outcome"], draft["band"]) == ("APPROVE", "REDUCED")
    assert Decimal(draft["recommended_amount"]) == Decimal("637000")
    assert [f["code"] for f in draft["factors"]] == ["sector_outlook"]

    missing = post_draft(client, db_app, tenant, case_id, payload("637420"))
    assert missing.status_code == 422
    assert "what lowered the amount" in missing.json()["error"]["message"]


def test_below_20_percent_is_a_decline(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    case_id = resolved_case(client, db_app, tenant)
    draft = post_draft(client, db_app, tenant, case_id, payload("150000")).json()
    assert (draft["outcome"], draft["band"]) == ("DECLINE", "DECLINE")
    assert draft["recommended_amount"] is None and draft["rule_codes"] == ["amount_below_floor"]


def test_weak_consolidated_financials_mean_decline_and_need_no_amount(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    body = payload(None, financial_findings_weak=True)
    draft = post_draft(client, db_app, tenant, case_id, body).json()
    assert draft["outcome"] == "DECLINE" and draft["rule_codes"] == ["financial_findings_weak"]


def test_a_verified_finding_means_decline_whatever_the_amount(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    finding = {"code": "sanctions", "verified": True, "evidence": [WEB]}
    draft = post_draft(
        client, db_app, tenant, case_id, payload("1000000", decline_findings=[finding])
    ).json()
    assert draft["outcome"] == "DECLINE" and draft["rule_codes"] == ["sanctions"]
    assert draft["decline_findings"][0]["verified"] is True


def test_an_unverified_finding_is_not_a_decline_it_blocks_the_draft(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    finding = {"code": "insolvency", "verified": False, "evidence": [WEB]}
    response = post_draft(
        client, db_app, tenant, case_id, payload("900000", decline_findings=[finding])
    )
    assert response.status_code == 422
    assert "not verified" in response.json()["error"]["message"]
    assert (
        client.get(
            f"{CASES}/{case_id}/draft-recommendations",
            headers=headers(db_app, "underwriter", tenant),
        ).json()
        == []
    )


def test_the_author_cannot_choose_the_outcome_or_amount(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    for field, value in (
        ("outcome", "APPROVE"),
        ("recommended_amount", "999999"),
        ("band", "FULL"),
    ):
        response = post_draft(client, db_app, tenant, case_id, payload("100000", **{field: value}))
        assert response.status_code == 422, field


def test_amounts_above_the_request_or_without_a_request_are_refused(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    assert post_draft(client, db_app, tenant, case_id, payload("1000001")).status_code == 422
    assert post_draft(client, db_app, tenant, case_id, payload(None)).status_code == 422
    no_request = resolved_case(client, db_app, tenant, exposure=None)
    response = post_draft(client, db_app, tenant, no_request, payload("500000"))
    assert (
        response.status_code == 422 and "requested exposure" in response.json()["error"]["message"]
    )


# --- the entity gate -------------------------------------------------------------------------


@pytest.mark.parametrize("candidates", [0, 2])
def test_an_unresolved_entity_cannot_have_a_draft(
    client: TestClient, db_app: FastAPI, tenant: str, candidates: int
) -> None:
    case = make_case(client, db_app, tenant, exposure_amount="1000000", exposure_currency="CAD")
    for n in range(candidates):
        client.post(
            f"{CASES}/{case['id']}/entity-candidates",
            json={"legal_name": f"Acme {n}"},
            headers=headers(db_app, "underwriter", tenant),
        )
    response = post_draft(client, db_app, tenant, str(case["id"]), payload("900000"))
    assert response.status_code == 409
    assert "resolved" in response.json()["error"]["message"]


def test_an_unconfirmed_entity_gives_a_decline_with_no_request_needed(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)  # no exposure on the case
    client.post(
        f"{CASES}/{case['id']}/entity-resolution/unconfirmed",
        json={"reason": "No registry match"},
        headers=headers(db_app, "underwriter", tenant),
    )
    draft = post_draft(client, db_app, tenant, str(case["id"]), payload(None)).json()
    assert draft["outcome"] == "DECLINE" and draft["rule_codes"] == ["entity_not_confirmed"]
    assert draft["requested_amount"] is None and draft["recommended_amount"] is None


# --- evidence (P-02: no invented evidence) ---------------------------------------------------


def make_document(db_app: FastAPI, tenant: str, case_id: str) -> str:
    record = db_app.state.document_store.add(
        case_id=uuid.UUID(case_id),
        tenant_id=tenant,
        category=__import__("app.documents.schemas", fromlist=["x"]).DocumentCategory.SUPPORTING,
        filename="statement.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256="0" * 64,
        storage_key=f"{tenant}/{uuid.uuid4().hex}/{uuid.uuid4().hex}",
        uploaded_by="underwriter-1",
    )
    return str(record.id)


def document_ref(document_id: str) -> dict[str, Any]:
    return {
        "kind": "document",
        "document_id": document_id,
        "quote": "Current assets 6,500",
        "location": "p. 12",
    }


def test_a_cited_document_must_be_a_real_upload_of_this_case(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    other_case = resolved_case(client, db_app, tenant)
    mine = make_document(db_app, tenant, case_id)
    foreign = make_document(db_app, tenant, other_case)

    def with_doc(doc: str) -> dict[str, Any]:
        return payload(
            "900000", reasons=[{"text": "From the balance sheet.", "evidence": [document_ref(doc)]}]
        )

    assert post_draft(client, db_app, tenant, case_id, with_doc(mine)).status_code == 201
    for bad in (foreign, str(uuid.uuid4())):
        response = post_draft(client, db_app, tenant, case_id, with_doc(bad))
        assert response.status_code == 422
        assert "not part of this case" in response.json()["error"]["message"]


@pytest.mark.parametrize(
    "evidence",
    [
        {
            "kind": "web",
            "url": "http://registry.example.org/x",
            "retrieved_at": "2026-10-07T12:00:00Z",
            "quote": "q",
        },
        {"kind": "web", "url": "https://registry.example.org/x", "quote": "q"},
        {"kind": "web", "quote": "q", "retrieved_at": "2026-10-07T12:00:00Z"},
        {"kind": "document", "quote": "q"},
        {
            "kind": "document",
            "document_id": str(uuid.uuid4()),
            "url": "https://x.example/y",
            "quote": "q",
        },
        {
            "kind": "web",
            "url": "https://registry.example.org/x",
            "retrieved_at": "2026-10-07T12:00:00Z",
        },
        {"kind": "rumour", "quote": "q"},
    ],
    ids=["http", "no_date", "no_url", "doc_no_id", "doc_with_url", "no_quote", "bad_kind"],
)
def test_evidence_must_be_complete_and_well_formed(
    client: TestClient, db_app: FastAPI, tenant: str, evidence: dict[str, Any]
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    body = payload("900000", reasons=[{"text": "A reason.", "evidence": [evidence]}])
    assert post_draft(client, db_app, tenant, case_id, body).status_code == 422


def test_every_reason_needs_evidence_and_the_draft_needs_reasons(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    assert (
        post_draft(client, db_app, tenant, case_id, payload("900000", reasons=[])).status_code
        == 422
    )
    no_evidence = payload("900000", reasons=[{"text": "Unsupported claim.", "evidence": []}])
    assert post_draft(client, db_app, tenant, case_id, no_evidence).status_code == 422


def test_only_the_approved_policy_version_and_source_are_accepted(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    for source in ({**SOURCE, "policy_version": "0.9"}, {**SOURCE, "kind": "anonymous"}):
        response = post_draft(client, db_app, tenant, case_id, payload("900000", source=source))
        assert response.status_code == 422


def test_duplicate_factors_and_findings_are_refused(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    factor = {"code": "concentration", "explanation": "Two customers are 60% of revenue."}
    body = payload("500000", factors=[factor, factor])
    assert post_draft(client, db_app, tenant, case_id, body).status_code == 422


# --- labels, versions, immutability ----------------------------------------------------------


def test_every_draft_is_labelled_and_states_the_payment_limitation(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    draft = post_draft(client, db_app, tenant, case_id, payload("900000")).json()
    assert draft["notice"] == NOTICE and draft["test_product"] is True
    assert draft["limitations"] == [
        "Payment behaviour was not assessed (data not used in this product)."
    ]
    assert draft["policy_version"] == "1.0" and draft["source"]["kind"] == "claude_code_session"


def test_new_drafts_get_new_versions_and_old_ones_are_kept(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    first = post_draft(client, db_app, tenant, case_id, payload("900000")).json()
    second = post_draft(client, db_app, tenant, case_id, payload("150000")).json()
    assert (first["version"], second["version"]) == (1, 2)
    h = headers(db_app, "auditor", tenant)
    listed = client.get(f"{CASES}/{case_id}/draft-recommendations", headers=h).json()
    assert [d["version"] for d in listed] == [2, 1]  # newest first, nothing overwritten
    one = client.get(f"{CASES}/{case_id}/draft-recommendations/{first['id']}", headers=h).json()
    assert one["outcome"] == "APPROVE"


def test_a_draft_cannot_be_fetched_through_another_case_or_when_unknown(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_a = resolved_case(client, db_app, tenant)
    case_b = resolved_case(client, db_app, tenant)
    draft = post_draft(client, db_app, tenant, case_a, payload("900000")).json()
    h = headers(db_app, "reviewer", tenant)
    assert (
        client.get(f"{CASES}/{case_b}/draft-recommendations/{draft['id']}", headers=h).status_code
        == 404
    )
    assert (
        client.get(f"{CASES}/{case_a}/draft-recommendations/{uuid.uuid4()}", headers=h).status_code
        == 404
    )


def test_drafts_cannot_be_edited_or_deleted_in_the_database(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    post_draft(client, db_app, tenant, case_id, payload("900000"))
    engine = db_app.state.draft_store._engine
    for statement in (
        "UPDATE draft_recommendations SET outcome = 'DECLINE'",
        "DELETE FROM draft_recommendations",
        "TRUNCATE draft_recommendations",
    ):
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
            conn.execute(sa.text(statement))


def test_the_database_itself_refuses_an_amount_above_the_request(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    engine = db_app.state.draft_store._engine
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO draft_recommendations (id, case_id, tenant_id, version, outcome, band,"
                " requested_amount, requested_currency, recommended_amount, rule_codes, content,"
                " source, policy_version, created_by, created_at) VALUES (:id, :case, :t, 99,"
                " 'APPROVE', 'FULL', 100, 'CAD', 200, '[]', '{}', '{}', '1.0', 'x', :now)"
            ),
            {"id": uuid.uuid4(), "case": case_id, "t": tenant, "now": datetime.now(UTC)},
        )


# --- permissions, tenants, audit -------------------------------------------------------------


@pytest.mark.parametrize("role", ["underwriter", "reviewer", "service"])
def test_roles_that_may_import_a_draft(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    assert post_draft(client, db_app, tenant, case_id, payload("900000"), role).status_code == 201


@pytest.mark.parametrize("role", ["research_analyst", "auditor", "administrator"])
def test_other_roles_cannot_import_a_draft(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    assert post_draft(client, db_app, tenant, case_id, payload("900000"), role).status_code == 403


@pytest.mark.parametrize("role", ["administrator", "service"])
def test_roles_without_case_read_cannot_read_drafts(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    draft = post_draft(client, db_app, tenant, case_id, payload("900000")).json()
    h = headers(db_app, role, tenant)
    assert client.get(f"{CASES}/{case_id}/draft-recommendations", headers=h).status_code == 403
    assert (
        client.get(f"{CASES}/{case_id}/draft-recommendations/{draft['id']}", headers=h).status_code
        == 403
    )


def test_unauthenticated_requests_are_refused(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    assert client.get(f"{CASES}/{case_id}/draft-recommendations").status_code == 401
    assert client.post(f"{CASES}/{case_id}/draft-recommendations", json={}).status_code == 401


def test_another_tenant_cannot_import_list_or_read_and_is_audited(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    draft = post_draft(client, db_app, tenant, case_id, payload("900000")).json()
    other = f"{tenant}-other"
    intruder = headers(db_app, "underwriter", other)
    results = [
        post_draft(client, db_app, other, case_id, payload("900000")),
        client.get(f"{CASES}/{case_id}/draft-recommendations", headers=intruder),
        client.get(f"{CASES}/{case_id}/draft-recommendations/{draft['id']}", headers=intruder),
    ]
    assert [r.status_code for r in results] == [404, 404, 404]
    assert [e.action for e in audit(db_app, other)] == ["authz.cross_tenant_denied"] * 3


def test_import_is_audited_without_outcomes_amounts_or_reasons(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    draft = post_draft(client, db_app, tenant, case_id, payload("900000")).json()
    imported = [e for e in audit(db_app, tenant) if e.action == "draft.imported"]
    assert len(imported) == 1
    assert imported[0].details == {
        "draft_id": draft["id"],
        "version": "1",
        "source": "claude_code_session",
    }
    text = str(imported[0])
    assert "APPROVE" not in text and "1000000" not in text and "Current ratio" not in text
