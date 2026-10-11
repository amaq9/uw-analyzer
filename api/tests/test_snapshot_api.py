"""Reading a stored snapshot: scoped to the case, hash-checked, audited."""

import hashlib
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.research.snapshots import SnapshotStore
from tests.test_cases_api import audit, headers
from tests.test_draft_recommendations import resolved_case
from tests.test_public_connectors import MemoryStorage


@pytest.fixture
def client(db_app: FastAPI) -> TestClient:
    return TestClient(db_app)


@pytest.fixture
def storage(db_app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> MemoryStorage:
    memory = MemoryStorage()
    monkeypatch.setattr(db_app.state, "document_service", SimpleNamespace(storage=memory))
    return memory


def test_reads_the_exact_bytes_and_audits(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    snap = SnapshotStore(storage).save(tenant, uuid.UUID(case_id), b'{"hello": "registry"}')
    h = headers(db_app, "auditor", tenant)
    r = client.get(f"/api/v1/cases/{case_id}/snapshots", params={"ref": snap.ref}, headers=h)
    assert r.status_code == 200 and r.content == b'{"hello": "registry"}'
    assert r.headers["x-content-type-options"] == "nosniff"
    event = next(e for e in audit(db_app, tenant) if e.action == "snapshot.read")
    assert event.details == {"sha256": snap.sha256}


def test_tampered_or_foreign_snapshots_are_refused(
    client: TestClient, db_app: FastAPI, tenant: str, storage: MemoryStorage
) -> None:
    case_id = resolved_case(client, db_app, tenant)
    other_case = resolved_case(client, db_app, tenant)
    h = headers(db_app, "underwriter", tenant)
    snap = SnapshotStore(storage).save(tenant, uuid.UUID(case_id), b"original")
    url = f"/api/v1/cases/{case_id}/snapshots"
    # another case of the same tenant cannot read it
    assert (
        client.get(
            f"/api/v1/cases/{other_case}/snapshots", params={"ref": snap.ref}, headers=h
        ).status_code
        == 404
    )
    # another tenant cannot read it
    assert (
        client.get(
            url, params={"ref": snap.ref}, headers=headers(db_app, "underwriter", tenant + "-x")
        ).status_code
        == 404
    )
    # the stored bytes no longer match the recorded hash
    storage.objects[snap.key] = b"tampered"
    assert client.get(url, params={"ref": snap.ref}, headers=h).status_code == 502
    # malformed references and wrong hashes
    for ref in (
        "snapshot://../../etc/passwd#sha256=" + "0" * 64,
        "https://x",
        "snapshot://snapshots/a/b/c",
    ):
        assert client.get(url, params={"ref": ref}, headers=h).status_code == 422
    good = hashlib.sha256(b"x").hexdigest()
    missing = f"snapshot://snapshots/{tenant}/{case_id}/{'a' * 32}#sha256={good}"
    assert client.get(url, params={"ref": missing}, headers=h).status_code == 404
