"""Uploaded statements: suggestions, confirmation, and analysis from confirmed figures (real Postgres)."""

import hashlib
import uuid
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.documents.schemas import DocumentCategory
from tests.statement_files import SECOND_YEAR_FIGURES, pdf_bytes, text_bytes
from tests.test_cases_api import audit, headers, make_case
from tests.test_public_connectors import MemoryStorage


class FakeService:
    """Stands in for the upload service: same store, in-memory file storage."""

    def __init__(self, store: Any, storage: MemoryStorage) -> None:
        self.store, self.storage = store, storage

    def open(self, record: Any) -> Iterator[bytes]:
        yield from self.storage.get(record.storage_key)


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


@pytest.fixture
def storage(db_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    memory = MemoryStorage()
    service = FakeService(db_app.state.document_store, memory)
    monkeypatch.setattr(db_app.state, "document_service", service)
    return memory


def add_document(
    app: FastAPI, storage: MemoryStorage, tenant: str, case_id: str, name: str, data: bytes
) -> str:
    key = f"docs/{tenant}/{uuid.uuid4().hex}"
    storage.objects[key] = data
    record = app.state.document_store.add(
        case_id=uuid.UUID(case_id),
        tenant_id=tenant,
        category=DocumentCategory.FINANCIAL_STATEMENT,
        filename=name,
        content_type="application/pdf" if name.endswith(".pdf") else "text/plain",
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        storage_key=key,
        uploaded_by="underwriter-1",
    )
    return str(record.id)


def private_case(
    client: TestClient, app: FastAPI, tenant: str, **kw: Any
) -> tuple[str, dict[str, str]]:
    case = make_case(
        client,
        app,
        tenant,
        legal_name="Acme Holdings Ltd",
        exposure_amount="1000000",
        exposure_currency="CAD",
        **kw,
    )
    h = headers(app, "underwriter", tenant)
    cand = client.post(
        f"/api/v1/cases/{case['id']}/entity-candidates",
        json={"legal_name": "Acme Holdings Ltd"},
        headers=h,
    ).json()
    client.post(
        f"/api/v1/cases/{case['id']}/entity-resolution",
        json={"candidate_id": cand["id"]},
        headers=h,
    )
    return case["id"], h


def confirm_body(document_id: str, audit_status: str = "AUDITED", **kw: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "document_id": document_id,
        "currency": "CAD",
        "unit": "thousands",
        "audit_status": audit_status,
        "periods": [
            {"period_end": "2025-12-31", "figures": SECOND_YEAR_FIGURES},
            {
                "period_end": "2024-12-31",
                "figures": {
                    "total_assets": 36500,
                    "total_equity": 13213,
                    "current_assets": 23300,
                    "current_liabilities": 10566,
                    "cash": 7464,
                    "receivables": 4717,
                    "inventory": 7489,
                    "debt_noncurrent": 7961,
                    "debt_current": 0,
                    "revenue": 46309,
                    "net_income": 3219,
                    "ocf": 3698,
                    "capex": 430,
                    "dividends": 2300,
                    "buybacks": 2985,
                },
            },
        ],
    }
    body.update(kw)
    return body


def test_preview_suggests_figures_from_a_pdf_without_saving_anything(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = private_case(client, db_app, tenant)
    doc = add_document(db_app, storage, tenant, case_id, "accounts.pdf", pdf_bytes())
    r = client.get(f"/api/v1/cases/{case_id}/documents/{doc}/figures-preview", headers=h)
    assert r.status_code == 200, r.text
    out = r.json()
    assert (
        out["periods"] == ["2025", "2024"]
        and out["unit_guess"] == "thousands"
        and out["currency_guess"] == "CAD"
    )
    rows = {row["metric"]: row for row in out["rows"]}
    assert (
        rows["total_assets"]["values"] == [38400.0, 36500.0]
        and rows["total_assets"]["label"] == "Total assets"
    )
    assert "Nothing is used until you confirm" in out["notice"]
    assert {m["metric"] for m in out["metrics"]} >= {"total_assets", "revenue", "ocf"}
    assert client.get(f"/api/v1/cases/{case_id}/statements", headers=h).json() == []


def test_unreadable_and_foreign_documents_are_refused(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = private_case(client, db_app, tenant)
    bad = add_document(db_app, storage, tenant, case_id, "scan.pdf", b"%PDF-1.4 broken")
    assert (
        client.get(
            f"/api/v1/cases/{case_id}/documents/{bad}/figures-preview", headers=h
        ).status_code
        == 422
    )
    other_case, _ = private_case(client, db_app, tenant)
    doc = add_document(db_app, storage, tenant, other_case, "accounts.pdf", pdf_bytes())
    assert (
        client.get(
            f"/api/v1/cases/{case_id}/documents/{doc}/figures-preview", headers=h
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/cases/{case_id}/documents/{uuid.uuid4()}/figures-preview", headers=h
        ).status_code
        == 404
    )
    foreign = headers(db_app, "underwriter", tenant + "-x")
    assert (
        client.get(
            f"/api/v1/cases/{other_case}/documents/{doc}/figures-preview", headers=foreign
        ).status_code
        == 404
    )
    for role in ("auditor", "research_analyst", "administrator"):
        r = client.get(
            f"/api/v1/cases/{other_case}/documents/{doc}/figures-preview",
            headers=headers(db_app, role, tenant),
        )
        assert r.status_code == 403


@pytest.mark.parametrize(
    "mutation",
    [
        {"currency": "cad"},
        {"unit": "billions"},
        {"audit_status": "TRUSTED"},
        {"periods": []},
        {"periods": [{"period_end": "2025-12-31", "figures": {"total_assets": 1}}]},
        {
            "periods": [
                {
                    "period_end": "2025-12-31",
                    "figures": {"total_assets": 1, "revenue": 2, "ocf": 3, "made_up": 4},
                }
            ]
        },
        {
            "periods": [
                {"period_end": "2999-12-31", "figures": {"total_assets": 1, "revenue": 2, "ocf": 3}}
            ]
        },
        {"extra": "field"},
    ],
    ids=[
        "currency",
        "unit",
        "audit",
        "no-periods",
        "too-few",
        "unknown-metric",
        "future",
        "extra-field",
    ],
)
def test_bad_confirmations_are_refused(
    client: TestClient,
    db_app: FastAPI,
    tenant: str,
    storage: MemoryStorage,
    mutation: dict[str, Any],
) -> None:
    case_id, h = private_case(client, db_app, tenant)
    doc = add_document(db_app, storage, tenant, case_id, "accounts.pdf", pdf_bytes())
    r = client.post(
        f"/api/v1/cases/{case_id}/statements", json=confirm_body(doc, **mutation), headers=h
    )
    assert r.status_code == 422
    assert client.get(f"/api/v1/cases/{case_id}/statements", headers=h).json() == []


def test_confirmation_is_recorded_listed_audited_and_a_later_one_replaces_it(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = private_case(client, db_app, tenant)
    doc = add_document(db_app, storage, tenant, case_id, "accounts.pdf", pdf_bytes())
    r = client.post(f"/api/v1/cases/{case_id}/statements", json=confirm_body(doc), headers=h)
    assert r.status_code == 201, r.text
    assert [s["period_end"] for s in r.json()] == ["2025-12-31", "2024-12-31"]
    assert all(s["confirmed_by"] == "underwriter-1" for s in r.json())

    corrected = confirm_body(doc)
    corrected["periods"] = [
        {"period_end": "2025-12-31", "figures": {**SECOND_YEAR_FIGURES, "revenue": 50000}}
    ]
    client.post(f"/api/v1/cases/{case_id}/statements", json=corrected, headers=h)
    current = client.get(
        f"/api/v1/cases/{case_id}/statements", headers=headers(db_app, "auditor", tenant)
    ).json()
    assert [s["period_end"] for s in current] == ["2025-12-31", "2024-12-31"]  # newest period first
    assert current[0]["figures"]["revenue"] == 50000  # the later confirmation is the one in use
    event = next(e for e in audit(db_app, tenant) if e.action == "statement.confirmed")
    assert set(event.details) == {"document_id", "periods"}


def test_confirmed_figures_cannot_be_edited_or_deleted_in_the_database(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    import sqlalchemy as sa
    from sqlalchemy.exc import DBAPIError

    case_id, h = private_case(client, db_app, tenant)
    doc = add_document(db_app, storage, tenant, case_id, "accounts.pdf", pdf_bytes())
    client.post(f"/api/v1/cases/{case_id}/statements", json=confirm_body(doc), headers=h)
    engine = db_app.state.statement_store._engine
    for sql in (
        "UPDATE financial_statements SET notes = 'x'",
        "DELETE FROM financial_statements",
        "TRUNCATE financial_statements",
    ):
        with pytest.raises(DBAPIError), engine.begin() as conn:
            conn.execute(sa.text(sql))


def test_a_private_company_is_analysed_from_confirmed_uploaded_statements(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = private_case(client, db_app, tenant)
    doc = add_document(db_app, storage, tenant, case_id, "accounts.pdf", pdf_bytes())
    client.post(f"/api/v1/cases/{case_id}/statements", json=confirm_body(doc, "AUDITED"), headers=h)
    r = client.post(
        f"/api/v1/cases/{case_id}/analysis", json={}, headers=h
    )  # no research run at all
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "DRAFT_PREPARED" and out["periods_reviewed"] == [
        "2025-12-31",
        "2024-12-31",
    ]
    assert out["currency"] == "CAD" and out["draft"]["source"]["kind"] == "analyzer_v1"
    assert any(
        "uploaded document" in g and "confirmed by underwriter-1" in g
        for g in out["information_gaps"]
    )
    assert any("audited" in g for g in out["information_gaps"])
    derived = [g for g in out["information_gaps"] if g.startswith("Figure derived")]
    assert len(derived) == len(set(derived))  # each note once
    assert "0.75" not in out["draft"]["summary"] or "CAD" in out["draft"]["summary"]
    ev = client.get(f"/api/v1/cases/{case_id}/evidence", headers=h).json()[0]
    assert (
        ev["kind"] == "DOCUMENT" and ev["document_id"] == doc and ev["source_class"] == "COMMERCIAL"
    )
    assert ev["source_class_basis"] == "author_declared" and ev["event_on"] == "2025-12-31"
    claims = client.get(f"/api/v1/cases/{case_id}/claims", headers=h).json()
    facts = [c for c in claims if c["classification"] == "FACT"]
    assert facts
    # one company-supplied source verifies an ordinary finding; a warning sign (adverse) needs a
    # second independent source or an official primary one (FR-3.7), so it stays partly verified
    assert {c["verification"]["status"] for c in facts if not c["adverse"]} == {"VERIFIED"}
    assert {c["verification"]["status"] for c in facts if c["adverse"]} <= {"PARTIALLY_VERIFIED"}
    reason_ev = out["draft"]["reasons"][0]["evidence"][0]
    assert reason_ev["kind"] == "document" and reason_ev["document_id"] == doc


def test_unaudited_company_statements_count_as_weaker_evidence(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = private_case(client, db_app, tenant)
    doc = add_document(db_app, storage, tenant, case_id, "management.pdf", pdf_bytes())
    client.post(
        f"/api/v1/cases/{case_id}/statements", json=confirm_body(doc, "UNAUDITED"), headers=h
    )
    out = client.post(f"/api/v1/cases/{case_id}/analysis", json={}, headers=h).json()
    assert any("NOT audited" in g for g in out["information_gaps"])
    ev = client.get(f"/api/v1/cases/{case_id}/evidence", headers=h).json()[0]
    assert ev["source_class"] == "SECONDARY"
    claims = client.get(f"/api/v1/cases/{case_id}/claims", headers=h).json()
    statuses = {c["verification"]["status"] for c in claims if c["classification"] == "FACT"}
    assert statuses == {"PARTIALLY_VERIFIED"}  # weak evidence alone cannot verify a material claim


def test_analysis_says_what_is_missing_for_uploads(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = private_case(client, db_app, tenant)
    none_yet = client.post(
        f"/api/v1/cases/{case_id}/analysis", json={"financials": "uploaded"}, headers=h
    )
    assert (
        none_yet.status_code == 409 and "Upload a statement" in none_yet.json()["error"]["message"]
    )
    plain = client.post(f"/api/v1/cases/{case_id}/analysis", json={}, headers=h)
    assert plain.status_code == 409 and "research" in plain.json()["error"]["message"].lower()

    doc = add_document(db_app, storage, tenant, case_id, "accounts.pdf", pdf_bytes())
    client.post(
        f"/api/v1/cases/{case_id}/statements", json=confirm_body(doc, currency="USD"), headers=h
    )
    mismatch = client.post(f"/api/v1/cases/{case_id}/analysis", json={}, headers=h)
    assert mismatch.status_code == 409 and "currency" in mismatch.json()["error"]["message"].lower()


def test_text_files_work_too(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = private_case(client, db_app, tenant)
    doc = add_document(db_app, storage, tenant, case_id, "accounts.txt", text_bytes())
    r = client.get(f"/api/v1/cases/{case_id}/documents/{doc}/figures-preview", headers=h)
    assert r.status_code == 200 and r.json()["unit_guess"] == "thousands"
    assert date.fromisoformat(r.json()["period_end_guesses"][0]) == date(2025, 12, 31)
