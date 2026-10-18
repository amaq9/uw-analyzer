"""The sources the seed script registers are valid, and the rating agencies are among them."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.seed_sources import SOURCES
from tests.test_cases_api import headers


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def test_every_seeded_source_is_accepted_by_the_registry(
    client: TestClient, db_app: FastAPI, tenant: str
) -> None:
    for source in SOURCES:
        r = client.post(
            "/api/v1/sources", json=source, headers=headers(db_app, "administrator", tenant)
        )
        assert r.status_code == 201, (source["key"], r.text)
    assert len({s["key"] for s in SOURCES}) == len(SOURCES)  # no duplicate keys


def test_the_three_rating_agencies_are_registered_as_the_main_sources_for_ratings() -> None:
    agencies = {s["key"]: s for s in SOURCES if s["source_type"] == "credit_rating_agency"}
    assert set(agencies) == {"sp-global-ratings", "moodys-ratings", "fitch-ratings"}
    notes = {key: str(source["terms_notes"]) for key, source in agencies.items()}
    assert "www.spglobal.com" in notes["sp-global-ratings"]
    assert "ratings.moodys.com" in notes["moodys-ratings"]
    assert "www.fitchratings.com" in notes["fitch-ratings"]
    for source in agencies.values():
        # Honest about access: licensed, no credential held, never fetched by the product.
        assert source["access_category"] == "RESTRICTED_LICENSED"
        assert source["auth_state"] == "MISSING"
        assert "does not fetch it" in str(source["terms_notes"])
