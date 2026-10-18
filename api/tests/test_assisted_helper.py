"""The assisted-mode helper script works end to end against a real Postgres and cannot decide."""

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts import assisted
from tests.test_draft_recommendations import payload, resolved_case


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


def test_read_and_submit_through_the_helper(
    client: TestClient,
    db_app: FastAPI,
    database_url: str,
    tenant: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The helper fills in missing settings; register each with monkeypatch so none leak into
    # other tests (config tests rely on a clean environment).
    for key, value in assisted.DEFAULTS.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("ASSISTED_TENANT", tenant)
    case_id = resolved_case(client, db_app, tenant)

    assert assisted.main(["case", case_id]) == 0
    assert "Acme" in capsys.readouterr().out

    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps(payload("900000")), encoding="utf-8")
    assert assisted.main(["submit", case_id, str(draft)]) == 0
    assert "UW Analyzer recommendation for the underwriter" in capsys.readouterr().out

    draft.write_text(json.dumps(payload("900000", surprise=1)), encoding="utf-8")
    assert assisted.main(["submit", case_id, str(draft)]) == 1
    assert assisted.main([]) == 2
    assert assisted.main(["cases"]) == 0


def test_helper_has_no_command_that_records_a_decision() -> None:
    source = Path(assisted.__file__).read_text(encoding="utf-8")
    for forbidden in ("/decision", "/resolution", "POST /reports", '/reports"', "/reopen"):
        assert forbidden not in source
