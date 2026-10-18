"""Published agency opinions: grade scales, recording with a source, append-only storage, access, audit,
and how they appear in the Step 1 report (information only; they never change the draft)."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from app.analysis.report import rating_flags, reconcile
from app.ratings.scale import SCALES, is_agency_site, is_investment_grade, normalise_grade
from app.ratings.schemas import PublishedRatingOut
from app.recommendation.analysis_report import AreaReport
from tests.test_analysis_api import analyse, prepared_case
from tests.test_analyzer_rules import DISTRESSED, STRONG
from tests.test_cases_api import CASES, audit, headers, make_case
from tests.test_public_connectors import MemoryStorage

SOURCE = "https://www.moodys.com/research/acme-corp-credit-opinion"


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


@pytest.fixture
def storage(db_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    memory = MemoryStorage()
    monkeypatch.setattr(db_app.state, "document_service", SimpleNamespace(storage=memory))
    return memory


def body(**kw: Any) -> dict[str, Any]:
    base = {
        "agency": "MOODYS",
        "grade": "Baa2",
        "outlook": "STABLE",
        "change": "AFFIRMED",
        "last_action_on": "2026-03-01",
        "rationale": "Stable margins and moderate leverage.",
        "source_url": SOURCE,
        "retrieved_at": "2026-10-10T12:00:00Z",
        "quote": "Moody's affirmed Acme Corp's Baa2 rating with a stable outlook.",
    }
    return {**base, **kw}


def post(
    client: TestClient,
    app: FastAPI,
    tenant: str,
    case_id: str,
    data: dict[str, Any],
    role: str = "underwriter",
) -> Any:
    return client.post(
        f"{CASES}/{case_id}/published-ratings", json=data, headers=headers(app, role, tenant)
    )


# --- the scales -----------------------------------------------------------------------------


def test_investment_grade_runs_to_baa3_and_bbb_minus() -> None:
    assert is_investment_grade("MOODYS", "Baa3") and not is_investment_grade("MOODYS", "Ba1")
    assert is_investment_grade("SP", "BBB-") and not is_investment_grade("SP", "BB+")
    assert is_investment_grade("FITCH", "BBB") and not is_investment_grade("FITCH", "B")
    # The supplied framework text put the line at A3 and A-: the agencies' scales are used instead.
    assert is_investment_grade("MOODYS", "Baa1") and is_investment_grade("SP", "BBB+")


def test_grades_are_checked_against_each_agencys_own_scale() -> None:
    assert normalise_grade("MOODYS", "baa2") == "Baa2"
    assert normalise_grade("SP", "bbb+") == "BBB+"
    assert normalise_grade("MOODYS", "BBB+") is None  # an S&P grade is not a Moody's grade
    assert normalise_grade("SP", "Baa2") is None
    assert normalise_grade("SP", "SD") == "SD" and normalise_grade("FITCH", "RD") == "RD"
    assert normalise_grade("FITCH", "SD") is None
    assert len(SCALES["MOODYS"]) == 21 and len(SCALES["SP"]) == 23


# --- recording, listing, replacing ----------------------------------------------------------


def test_a_rating_is_recorded_with_its_source_and_read_back(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    r = post(client, db_app, tenant, case["id"], body(grade="baa2"))
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["grade"] == "Baa2" and out["investment_grade"] is True
    assert out["source_url"] == SOURCE and out["recorded_by"] == "underwriter-1"
    assert "not this product's rating" in out["notice"]
    listed = client.get(
        f"{CASES}/{case['id']}/published-ratings", headers=headers(db_app, "auditor", tenant)
    ).json()
    assert [x["id"] for x in listed] == [out["id"]]


def test_a_newer_record_replaces_the_older_but_both_stay_on_record(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    post(client, db_app, tenant, case["id"], body(grade="Baa2"))
    post(client, db_app, tenant, case["id"], body(agency="SP", grade="BBB", change="NEW"))
    post(
        client,
        db_app,
        tenant,
        case["id"],
        body(grade="Ba1", change="DOWNGRADE", outlook="NEGATIVE"),
    )
    h = headers(db_app, "underwriter", tenant)
    latest = client.get(f"{CASES}/{case['id']}/published-ratings", headers=h).json()
    assert [(x["agency"], x["grade"]) for x in latest] == [("MOODYS", "Ba1"), ("SP", "BBB")]
    assert latest[0]["investment_grade"] is False
    everything = client.get(
        f"{CASES}/{case['id']}/published-ratings?latest=false", headers=h
    ).json()
    assert [x["grade"] for x in everything] == ["Ba1", "BBB", "Baa2"]  # newest first


def test_a_record_without_its_evidence_or_with_a_bad_grade_is_refused(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    tomorrow = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    bad_dates = {"last_action_on": (date.today() + timedelta(days=3)).isoformat()}
    cases = [
        body(source_url="http://www.moodys.com/x"),  # not secure
        body(source_url="moodys.com/x"),
        body(quote=""),
        body(retrieved_at=tomorrow),  # cannot have been read in the future
        body(grade="AA+"),  # an S&P grade, not a Moody's grade
        body(agency="SP", grade="Baa2"),  # not an S&P grade
        body(agency="DBRS"),
        body(outlook="GREAT"),
        body(**bad_dates),
        {k: v for k, v in body().items() if k != "source_url"},
        {k: v for k, v in body().items() if k != "retrieved_at"},
        {**body(), "extra": 1},
    ]
    for bad in cases:
        assert post(client, db_app, tenant, case["id"], bad).status_code == 422, bad
    h = headers(db_app, "underwriter", tenant)
    assert client.get(f"{CASES}/{case['id']}/published-ratings", headers=h).json() == []


def test_records_are_append_only_in_the_database_itself(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    post(client, db_app, tenant, case["id"], body())
    engine = db_app.state.rating_store._engine
    for statement in (
        "UPDATE published_ratings SET grade = 'Aaa'",
        "DELETE FROM published_ratings",
        "TRUNCATE published_ratings",
    ):
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
            conn.execute(sa.text(statement))


def test_the_database_refuses_a_record_with_no_source(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    engine = db_app.state.rating_store._engine
    with pytest.raises(DBAPIError), engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO published_ratings (id, tenant_id, case_id, agency, grade, outlook,"
                " under_review, change, source_url, retrieved_at, quote, recorded_by, recorded_at)"
                " VALUES (:id, :t, :c, 'MOODYS', 'Baa2', 'STABLE', false, 'NEW', 'not a link',"
                " now(), 'q', 'x', now())"
            ),
            {"id": uuid.uuid4(), "t": tenant, "c": case["id"]},
        )


# --- access and audit -----------------------------------------------------------------------


@pytest.mark.parametrize("role", ["underwriter", "reviewer", "service"])
def test_roles_that_may_record_a_rating(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    case = make_case(client, db_app, tenant)
    assert post(client, db_app, tenant, case["id"], body(), role).status_code == 201


@pytest.mark.parametrize("role", ["research_analyst", "auditor", "administrator"])
def test_other_roles_cannot_record_a_rating(
    client: TestClient, db_app: FastAPI, tenant: str, role: str
) -> None:
    case = make_case(client, db_app, tenant)
    assert post(client, db_app, tenant, case["id"], body(), role).status_code == 403


def test_recording_is_audited_without_the_content_and_other_tenants_are_refused(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    post(client, db_app, tenant, case["id"], body())
    event = next(e for e in audit(db_app, tenant) if e.action == "published_rating.recorded")
    assert event.details == {"agency": "MOODYS"}  # no grade, no reasons: that is case content
    other = f"{tenant}-other"
    intruder = headers(db_app, "underwriter", other)
    results = [
        post(client, db_app, other, case["id"], body()),
        client.get(f"{CASES}/{case['id']}/published-ratings", headers=intruder),
    ]
    assert [r.status_code for r in results] == [404, 404]
    assert [e.action for e in audit(db_app, other)] == ["authz.cross_tenant_denied"] * 2


def test_an_unknown_case_is_not_found(client: TestClient, db_app: FastAPI, tenant: str) -> None:
    assert post(client, db_app, tenant, str(uuid.uuid4()), body()).status_code == 404


# --- reading the ratings against the financial analysis -------------------------------------


def view(agency: str = "MOODYS", grade: str = "Baa2", **kw: Any) -> PublishedRatingOut:
    data = {
        "id": uuid.uuid4(),
        "case_id": uuid.uuid4(),
        "agency": agency,
        "grade": grade,
        "investment_grade": is_investment_grade(agency, grade),
        "outlook": "STABLE",
        "under_review": False,
        "change": "AFFIRMED",
        "last_action_on": date(2026, 3, 1),
        "rationale": None,
        "source_url": SOURCE,
        "retrieved_at": datetime(2026, 10, 10, tzinfo=UTC),
        "quote": "q",
        "recorded_by": "u",
        "recorded_at": datetime(2026, 10, 11, tzinfo=UTC),
    }
    return PublishedRatingOut(**{**data, **kw})


def areas(ok: int, weak: int, distressed: int) -> list[AreaReport]:
    statuses = ["OK"] * ok + ["WEAK"] * weak + ["DISTRESSED"] * distressed
    return [
        AreaReport(
            key=f"k{i}",
            title=f"T{i}",
            status=s,  # type: ignore[arg-type]
            finding="x",
            trend="Stable",
            why="w",
        )
        for i, s in enumerate(statuses)
    ]


def test_ratings_are_compared_with_the_financial_analysis_in_words() -> None:
    assert "nothing to compare" in reconcile(areas(4, 0, 0), [])
    assert "not a finding about the company" in reconcile(areas(4, 0, 0), [])
    same_good = reconcile(areas(4, 0, 0), [view()])
    assert "point the same way" in same_good and "investment grade" in same_good
    same_bad = reconcile(areas(1, 0, 3), [view(grade="Ba2")])
    assert "point the same way" in same_bad and "below investment grade" in same_bad
    assert "The two differ" in reconcile(areas(1, 0, 3), [view(grade="A2")])
    assert "The two differ" in reconcile(areas(4, 0, 0), [view(grade="B1")])
    assert "no alignment can be stated" in reconcile(areas(2, 1, 1), [view()])
    negative = reconcile(areas(4, 0, 0), [view(outlook="NEGATIVE")])
    assert "negative outlook or has a rating under review" in negative
    assert "under review" in reconcile(areas(4, 0, 0), [view(under_review=True)])


def test_rating_red_flags_need_a_recorded_rating_and_say_so_otherwise() -> None:
    none = rating_flags([], date(2026, 10, 18))
    assert len(none) == 4 and {f.state for f in none} == {"NOT_ASSESSABLE"}
    flags = {
        f.text: f
        for f in rating_flags(
            [
                view(change="DOWNGRADE", last_action_on=date(2026, 8, 1), outlook="NEGATIVE"),
                view("SP", "BB+", under_review=True),
            ],
            date(2026, 10, 18),
        )
    }
    assert flags["Recent downgrade by an agency (within 6 months)"].state == "TRIGGERED"
    assert flags["Negative outlook from an agency"].state == "TRIGGERED"
    assert flags["Speculative grade from an agency"].state == "TRIGGERED"
    assert "S&P BB+" in flags["Speculative grade from an agency"].detail
    assert flags["Rating under review by an agency"].state == "TRIGGERED"
    calm = {f.text: f.state for f in rating_flags([view()], date(2026, 10, 18))}
    assert set(calm.values()) == {"CLEAR"}
    old = rating_flags(
        [view(change="DOWNGRADE", last_action_on=date(2025, 1, 1))], date(2026, 10, 18)
    )
    assert old[0].state == "CLEAR"  # a downgrade more than six months ago is not recent


def test_the_report_carries_the_ratings_and_the_draft_is_unchanged_by_them(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    plain_id, h = prepared_case(client, db_app, tenant, storage, STRONG)
    plain = analyse(client, plain_id, h).json()
    assert plain["draft"]["analysis"]["published_ratings"] == []
    assert "nothing to compare" in plain["draft"]["analysis"]["ratings_reconciliation"]
    checks = {c["title"]: c for c in plain["draft"]["analysis"]["other_checks"]}
    assert checks["Published credit ratings"]["state"] == "NOT_SEARCHED"

    rated_id, h2 = prepared_case(client, db_app, f"{tenant}-r", storage, STRONG)
    h2 = headers(db_app, "underwriter", f"{tenant}-r")
    assert post(client, db_app, f"{tenant}-r", rated_id, body(grade="A2")).status_code == 201
    assert (
        post(
            client,
            db_app,
            f"{tenant}-r",
            rated_id,
            body(agency="FITCH", grade="BB", outlook="NEGATIVE"),
        ).status_code
        == 201
    )
    rated = analyse(client, rated_id, h2).json()
    report = rated["draft"]["analysis"]
    assert [(r["agency"], r["grade"]) for r in report["published_ratings"]] == [
        ("MOODYS", "A2"),
        ("FITCH", "BB"),
    ]
    assert report["ratings_reconciliation"].startswith(
        "The two differ"
    )  # mixed grades, sound financials
    flags = {f["text"]: f["state"] for f in report["red_flags"]}
    assert flags["Speculative grade from an agency"] == "TRIGGERED"
    assert flags["Negative outlook from an agency"] == "TRIGGERED"
    checks = {c["title"]: c for c in report["other_checks"]}
    assert checks["Published credit ratings"]["state"] == "FOUND"
    assert "Fitch BB" in checks["Published credit ratings"]["detail"]
    # Information only: the same figures give the same outcome and amount with or without ratings.
    assert rated["draft"]["outcome"] == plain["draft"]["outcome"]
    assert Decimal(rated["draft"]["recommended_amount"]) == Decimal(
        plain["draft"]["recommended_amount"]
    )
    assert rated["proposed_amount"] == plain["proposed_amount"]


def test_ratings_never_rescue_a_distressed_company(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = prepared_case(client, db_app, tenant, storage, DISTRESSED)
    post(client, db_app, tenant, case_id, body(grade="Aa2", outlook="POSITIVE"))
    out = analyse(client, case_id, h).json()
    assert out["draft"]["outcome"] == "DECLINE"
    assert out["draft"]["analysis"]["ratings_reconciliation"].startswith("The two differ")


# --- the agencies' own websites are the main sources ----------------------------------------


@pytest.mark.parametrize(
    ("agency", "url", "own_site"),
    [
        ("SP", "https://www.spglobal.com/ratings/en/research/articles/nike-a", True),
        ("SP", "https://spglobal.com/ratings", True),
        ("SP", "https://ratings.spglobal.com/x", True),
        ("SP", "https://WWW.SPGLOBAL.COM/ratings", True),  # host names are not case sensitive
        ("MOODYS", "https://ratings.moodys.com/ratings-news/123", True),
        ("MOODYS", "https://www.moodys.com/credit-ratings/Nike-Inc-credit-rating-1", True),
        ("FITCH", "https://www.fitchratings.com/research/corporate-finance/x", True),
        ("FITCH", "https://fitchratings.com/entity/nike", True),
        # Look-alikes and tricks never count as the agency's own site.
        ("SP", "https://evil-spglobal.com/ratings", False),
        ("SP", "https://notspglobal.com/ratings", False),
        ("SP", "https://spglobal.com.evil.org/ratings", False),
        ("SP", "https://www.spglobal.com@evil.org/ratings", False),
        ("SP", "https://evil.org/spglobal.com", False),
        ("FITCH", "https://www.fitchrating.com/x", False),  # missing 's': not Fitch's domain
        ("MOODYS", "https://moodys.com.evil.org/x", False),
        # Another agency's site is not this agency's site.
        ("MOODYS", "https://www.spglobal.com/ratings", False),
        ("SP", "https://ratings.moodys.com/x", False),
        # Press and aggregators are secondary sources.
        ("SP", "https://capital.com/en-au/news/nike-falls-after-s-p-cuts-rating", False),
        ("MOODYS", "https://www.sgieurope.com/financial/moodys-cuts-nikes-rating", False),
    ],
)
def test_the_agencys_own_website_is_the_main_source_and_lookalikes_never_count(
    agency: str, url: str, own_site: bool
) -> None:
    assert is_agency_site(agency, url) is own_site


def test_the_api_says_whether_a_rating_came_from_the_agencys_own_site(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    case = make_case(client, db_app, tenant)
    own = post(
        client,
        db_app,
        tenant,
        case["id"],
        body(agency="SP", grade="A", source_url="https://www.spglobal.com/ratings/en/x"),
    )
    press = post(
        client,
        db_app,
        tenant,
        case["id"],
        body(source_url="https://www.sgieurope.com/financial/moodys-cuts-nikes-rating"),
    )
    assert own.json()["source_kind"] == "AGENCY_SITE"
    assert press.json()["source_kind"] == "OTHER"  # accepted, but labelled secondary
    listed = client.get(
        f"{CASES}/{case['id']}/published-ratings", headers=headers(db_app, "auditor", tenant)
    ).json()
    assert {x["agency"]: x["source_kind"] for x in listed} == {
        "MOODYS": "OTHER",
        "SP": "AGENCY_SITE",
    }


def test_the_comparison_asks_for_confirmation_when_a_rating_came_from_a_secondary_source() -> None:
    press = view("SP", "A", source_url="https://capital.com/en-au/news/nike-falls")
    own = view("SP", "A", source_url="https://www.spglobal.com/ratings/en/x")
    secondary = reconcile(areas(4, 0, 0), [press])
    assert "S&P A came from a secondary source, not the agency's own website" in secondary
    assert "Confirm it on the agency's site, which is the main source." in secondary
    assert "secondary source" not in reconcile(areas(4, 0, 0), [own])
    mixed = reconcile(
        areas(4, 0, 0), [own, view("FITCH", "AA", source_url="https://example.org/x")]
    )
    assert "Fitch AA came from a secondary source" in mixed and "S&P A came" not in mixed
    both = reconcile(
        areas(4, 0, 0),
        [press, view("MOODYS", "A2", source_url="https://example.org/y")],
    )
    assert (
        "S&P A and Moody's A2 came from secondary sources, not the agencies' own websites" in both
    )
    assert "Confirm them on the agencies' sites, which are the main sources." in both


def test_the_research_check_names_the_secondary_ratings(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id, h = prepared_case(client, db_app, tenant, storage, STRONG)
    post(
        client,
        db_app,
        tenant,
        case_id,
        body(agency="SP", grade="A", source_url="https://www.spglobal.com/ratings/x"),
    )
    post(client, db_app, tenant, case_id, body(source_url="https://www.sgieurope.com/x"))
    checks = {
        c["title"]: c
        for c in analyse(client, case_id, h).json()["draft"]["analysis"]["other_checks"]
    }
    detail = checks["Published credit ratings"]["detail"]
    assert "Moody's Baa2 (secondary source)" in detail and "S&P A (secondary" not in detail
