"""Analysis endpoint end to end: real connectors (with fake web responses) -> snapshots -> findings
-> draft recommendation, all against a real Postgres."""

import json
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research.public_connectors import SecEdgarConnector
from app.research.screening_connectors import OfacSdnConnector
from app.research.snapshots import SnapshotStore
from tests.test_analyzer_rules import DISTRESSED, STRONG, facts_json
from tests.test_cases_api import audit, headers, make_case
from tests.test_public_connectors import FakeFetcher, MemoryStorage
from tests.test_research_executor import drain, executor, start
from tests.test_screening_connectors import alt_csv, sdn_csv
from tests.test_sources_api import register


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


@pytest.fixture
def storage(db_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    memory = MemoryStorage()
    monkeypatch.setattr(db_app.state, "document_service", SimpleNamespace(storage=memory))
    return memory


def connectors(
    storage: MemoryStorage,
    profile: dict[str, Any],
    sdn: list[str] | None = None,
    with_ofac: bool = False,
) -> list[Any]:
    tickers = {"0": {"cik_str": 111, "ticker": "ACME", "title": "Acme Corp"}}
    sec_fetcher = FakeFetcher(
        {
            "https://www.sec.gov/files/company_tickers.json": json.dumps(tickers).encode(),
            "https://data.sec.gov/submissions/CIK0000000111.json": b'{"filings": {}}',
            "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000111.json": json.dumps(
                facts_json(profile)
            ).encode(),
        }
    )
    out: list[Any] = [SecEdgarConnector(sec_fetcher, SnapshotStore(storage))]
    if with_ofac:
        base = "https://sanctionslistservice.ofac.treas.gov/api/publicationpreview/exports/"
        ofac_fetcher = FakeFetcher(
            {base + "sdn.csv": sdn_csv(sdn or []), base + "alt.csv": alt_csv([])}
        )
        out.append(OfacSdnConnector(ofac_fetcher, SnapshotStore(storage)))
    return out


def prepared_case(
    client: TestClient,
    app: FastAPI,
    tenant: str,
    storage: MemoryStorage,
    profile: dict[str, Any],
    *,
    ofac: bool = False,
    sdn: list[str] | None = None,
    exposure: str | None = "1000000",
) -> tuple[str, dict[str, str]]:
    register(
        client, app, tenant, key="sec-edgar", source_type="financial_filings", jurisdictions=["US"]
    )
    if ofac:
        register(
            client,
            app,
            tenant,
            key="ofac-sdn",
            source_type="sanctions_list",
            jurisdictions=["GLOBAL"],
        )
    extra: dict[str, Any] = (
        {"exposure_amount": exposure, "exposure_currency": "USD"} if exposure else {}
    )
    case = make_case(client, app, tenant, legal_name="Acme Corp", **extra)
    h = headers(app, "underwriter", tenant)
    cand = client.post(
        f"/api/v1/cases/{case['id']}/entity-candidates", json={"legal_name": "Acme Corp"}, headers=h
    ).json()
    client.post(
        f"/api/v1/cases/{case['id']}/entity-resolution",
        json={"candidate_id": cand["id"]},
        headers=h,
    )
    run = client.post(
        f"/api/v1/cases/{case['id']}/research-runs", json={"jurisdictions": ["US"]}, headers=h
    ).json()
    start(client, case["id"], run["id"], h)
    drain(executor(app, *connectors(storage, profile, sdn, ofac))[0])
    return case["id"], h


def analyse(client: TestClient, case_id: str, h: dict[str, str]) -> Any:
    return client.post(f"/api/v1/cases/{case_id}/analysis", json={}, headers=h)


def test_a_strong_company_gets_a_full_draft_with_findings_and_reasons(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = prepared_case(client, db_app, tenant, storage, STRONG)
    r = analyse(client, case_id, h)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["status"] == "DRAFT_PREPARED" and "not a decision" in out["message"]
    assert out["periods_reviewed"] == ["2026-05-31", "2025-05-31", "2024-05-31"]
    assert [s["key"] for s in out["sections"]] == [
        "balance_sheet",
        "liquidity",
        "gearing",
        "receivables",
        "cash_flow",
    ]
    assert {s["assessment"] for s in out["sections"]} <= {
        "STRONG",
        "SATISFACTORY",
        "NEEDS_ATTENTION",
        "WEAK",
        "NOT_ASSESSED",
    }
    assert out["consolidated_assessment"] in {"STRONG", "SATISFACTORY"}
    draft = out["draft"]
    assert (draft["outcome"], draft["band"]) == ("APPROVE", "FULL")
    assert Decimal(draft["recommended_amount"]) == Decimal(
        "1000000"
    )  # policy: 80% or more is the full amount
    assert draft["source"]["kind"] == "analyzer_v1" and draft["notice"].startswith(
        "Draft recommendation"
    )
    assert any("sector" in g.lower() for g in draft["information_gaps"])
    assert draft["limitations"]
    report = draft["analysis"]
    assert [a["key"] for a in report["areas"]] == [
        "balance_sheet",
        "liquidity",
        "gearing",
        "receivables",
        "cash_flow",
        "profitability",
        "efficiency",
    ]
    core = [a for a in report["areas"] if a["feeds_draft"]]
    context = [a for a in report["areas"] if not a["feeds_draft"]]
    assert len(core) == 5 and [a["key"] for a in context] == ["profitability", "efficiency"]
    assert next(a for a in context if a["key"] == "efficiency")["status"] == "NOT_ASSESSED"
    assert {a["status"] for a in report["areas"]} <= {"OK", "WEAK", "DISTRESSED", "NOT_ASSESSED"}
    profitability = next(a for a in context if a["key"] == "profitability")
    assert any(m["label"] == "Net margin" for m in profitability["metrics"])
    assert all("earlier" in m for a in report["areas"] for m in a["metrics"])
    assert report["executive_summary"].startswith("Consolidated financial findings")
    assert report["debt_service"] and report["debt_service_notes"]
    assert [r["scenario"] for r in report["stress"]] == [
        "As reported",
        "Revenue down 10%",
        "Revenue down 20%",
    ]
    assert "not a forecast" in report["stress_note"]
    assert report["consolidated_status"] == "OK"
    assert len(report["red_flags"]) == 16
    assert {f["state"] for f in report["red_flags"]} <= {"TRIGGERED", "CLEAR", "NOT_ASSESSABLE"}
    assert report["red_flags"][-1]["state"] == "NOT_ASSESSABLE"  # needs the printed statements
    liquidity = next(a for a in report["areas"] if a["key"] == "liquidity")
    assert liquidity["metrics"] and {"label", "current", "prior", "change"} <= set(
        liquidity["metrics"][0]
    )
    assert report["basis"]["periods"] == out["periods_reviewed"]
    assert report["strengths"] and report["watch"] and report["gaps"]
    assert {c["title"] for c in report["other_checks"]} >= {"Sector outlook", "Payment behaviour"}
    stored = client.get(
        f"/api/v1/cases/{case_id}/draft-recommendations/{draft['id']}", headers=h
    ).json()
    assert stored["analysis"] == report  # kept with the draft, not recomputed on read
    assert Decimal(out["proposed_amount"]) == Decimal("900000.00")  # 100% less 10% for two gaps
    assert [f["code"] for f in out["factors"]] == ["missing_information"]
    assert out["evidence_created"] == 1 and out["claims_created"] >= 6

    claims = client.get(f"/api/v1/cases/{case_id}/claims", headers=h).json()
    financial = [c for c in claims if c["category"] == "FINANCIALS"]
    assert {c["verification"]["status"] for c in financial if c["classification"] == "FACT"} == {
        "VERIFIED"
    }
    assert any(
        c["classification"] == "INTERPRETATION" and c["verification"]["status"] == "NOT_APPLICABLE"
        for c in financial
    )
    ev = client.get(f"/api/v1/cases/{case_id}/evidence", headers=h).json()[0]
    assert (
        ev["kind"] == "CONNECTOR"
        and ev["event_on"] == "2026-05-31"
        and ev["published_on"] == "2026-07-15"
    )
    assert ev["source_class_basis"] == "registry" and ev["connector_call_id"]


def test_running_it_again_makes_a_new_draft_version_without_duplicating_findings(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = prepared_case(client, db_app, tenant, storage, STRONG)
    first = analyse(client, case_id, h).json()
    second = analyse(client, case_id, h).json()
    assert (first["draft"]["version"], second["draft"]["version"]) == (1, 2)
    assert second["claims_created"] == 0 and second["evidence_created"] == 0
    assert len(client.get(f"/api/v1/cases/{case_id}/evidence", headers=h).json()) == 1


def test_a_distressed_company_gets_a_decline_draft_and_never_a_decision(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = prepared_case(client, db_app, tenant, storage, DISTRESSED)
    out = analyse(client, case_id, h).json()
    assert out["consolidated_assessment"] == "WEAK"
    draft = out["draft"]
    report = draft["analysis"]
    assert report["consolidated_status"] == "DISTRESSED"
    assert any(a["status"] == "DISTRESSED" for a in report["areas"])
    assert report["weaknesses"]
    assert report["key_concerns"][0].split(":")[1].strip().startswith("distressed")
    assert (draft["outcome"], draft["band"], draft["recommended_amount"]) == (
        "DECLINE",
        "DECLINE",
        None,
    )
    assert "financial_findings_weak" in draft["rule_codes"]
    decision = client.get(
        f"/api/v1/cases/{case_id}/draft-recommendations/{draft['id']}/decision", headers=h
    )
    assert decision.status_code == 404  # nothing was decided on anyone's behalf


def test_a_possible_sanctions_match_stops_for_a_person_and_makes_no_draft(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    sdn = ['901,"ACME CORP",-0- ,"SDGT",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ']
    case_id, h = prepared_case(client, db_app, tenant, storage, STRONG, ofac=True, sdn=sdn)
    out = analyse(client, case_id, h).json()
    assert out["status"] == "NEEDS_REVIEW" and out["draft"] is None and out["review_item_id"]
    items = client.get(f"/api/v1/cases/{case_id}/escalations", headers=h).json()
    assert items["open_count"] == 1 and items["items"][0]["raised_by_system"] is True
    assert client.get(f"/api/v1/cases/{case_id}/draft-recommendations", headers=h).json() == []


def test_a_clean_sanctions_search_is_recorded_as_a_finding(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = prepared_case(client, db_app, tenant, storage, STRONG, ofac=True)
    out = analyse(client, case_id, h).json()
    assert out["status"] == "DRAFT_PREPARED"
    claims = client.get(f"/api/v1/cases/{case_id}/claims", headers=h).json()
    ofac = next(c for c in claims if "OFAC" in c["text"])
    assert (
        ofac["verification"]["status"] == "VERIFIED"
        and "found no exact or possible match" in ofac["text"]
    )


def test_without_financials_or_exposure_it_says_what_is_missing(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = prepared_case(client, db_app, tenant, storage, STRONG, exposure=None)
    r = analyse(client, case_id, h)
    assert r.status_code == 409 and "requested exposure" in r.json()["error"]["message"]

    other = make_case(
        client,
        db_app,
        tenant,
        legal_name="Beta Ltd",
        exposure_amount="1000",
        exposure_currency="USD",
    )
    cand = client.post(
        f"/api/v1/cases/{other['id']}/entity-candidates", json={"legal_name": "Beta Ltd"}, headers=h
    ).json()
    client.post(
        f"/api/v1/cases/{other['id']}/entity-resolution",
        json={"candidate_id": cand["id"]},
        headers=h,
    )
    r2 = analyse(client, other["id"], h)
    assert r2.status_code == 409 and "research" in r2.json()["error"]["message"].lower()


def test_permissions_tenants_and_audit(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = prepared_case(client, db_app, tenant, storage, STRONG)
    for role in ("auditor", "research_analyst", "administrator"):
        assert analyse(client, case_id, headers(db_app, role, tenant)).status_code == 403
    assert (
        analyse(client, case_id, headers(db_app, "underwriter", tenant + "-x")).status_code == 404
    )
    assert analyse(client, case_id, h).status_code == 201
    event = next(e for e in audit(db_app, tenant) if e.action == "analysis.run")
    assert set(event.details) == {"result", "evidence_created", "claims_created"}
    assert "Acme" not in str(event.details)


def test_the_analysis_contract_has_no_score_rating_or_decision_fields() -> None:
    from scripts.export_openapi import build_spec
    from tests.p09 import offending_names

    assert offending_names(build_spec()) == []
