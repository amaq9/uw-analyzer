"""Upload endpoints against a real Postgres, with fake storage and a fake scanner so every failure
mode can be forced (the real S3 and ClamAV are covered in test_documents_integration.py)."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, BinaryIO

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from app.config import AppEnv, AuthMode, Settings
from app.documents.scanner import ScannerUnavailableError, ScanResult
from app.documents.service import MAX_DOCUMENTS_PER_CASE, DocumentService
from app.documents.storage import StorageUnavailableError
from app.documents.store import PostgresDocumentStore, case_documents
from app.main import create_app
from tests.files import EICAR, PDF_BYTES, office_zip, zip_bomb
from tests.test_cases_api import CASES, audit, headers, make_case


@dataclass
class FakeStorage:
    objects: dict[str, bytes] = field(default_factory=dict)
    fail_put: bool = False
    fail_get: bool = False
    deleted: list[str] = field(default_factory=list)

    def put(self, key: str, file: BinaryIO, size: int) -> None:
        if self.fail_put:
            raise StorageUnavailableError
        file.seek(0)
        self.objects[key] = file.read()

    def get(self, key: str) -> Iterator[bytes]:
        if self.fail_get:
            raise StorageUnavailableError
        yield self.objects[key]

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)


@dataclass
class FakeScanner:
    infected: bool = False
    down: bool = False
    scanned: int = 0

    def scan(self, file: BinaryIO) -> ScanResult:
        self.scanned += 1
        if self.down:
            raise ScannerUnavailableError("refused")
        file.seek(0)
        if self.infected or EICAR in file.read():
            return ScanResult(clean=False, signature="Test-Signature")
        return ScanResult(clean=True)


@dataclass
class Env:
    app: FastAPI
    client: TestClient
    storage: FakeStorage
    scanner: FakeScanner
    service: DocumentService


@pytest.fixture
def env(database_url: str, db_app: FastAPI) -> Env:  # db_app guarantees migrations are applied
    storage, scanner = FakeStorage(), FakeScanner()
    settings = Settings(app_env=AppEnv.TEST, auth_mode=AuthMode.STUB, database_url=database_url)
    store = PostgresDocumentStore(sa.create_engine(database_url))
    service = DocumentService(store=store, storage=storage, scanner=scanner, max_bytes=1024 * 1024)
    app = create_app(settings, document_service=service)
    return Env(app, TestClient(app), storage, scanner, service)


def upload(
    env: Env,
    tenant: str,
    case_id: str,
    data: bytes = PDF_BYTES,
    name: str = "statement.pdf",
    category: str = "financial_statement",
    role: str = "underwriter",
) -> Any:
    return env.client.post(
        f"{CASES}/{case_id}/documents",
        files={"file": (name, data, "application/octet-stream")},
        data={"category": category},
        headers=headers(env.app, role, tenant),
    )


def new_case(env: Env, tenant: str) -> str:
    return str(make_case(env.client, env.app, tenant)["id"])


# --- happy path ------------------------------------------------------------------------------


def test_upload_list_and_download_round_trip(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    response = upload(env, tenant, case_id)
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["filename"] == "statement.pdf"
    assert doc["content_type"] == "application/pdf"
    assert doc["size_bytes"] == len(PDF_BYTES)
    assert doc["scan_status"] == "clean"
    assert len(doc["sha256"]) == 64
    assert "storage_key" not in doc and "tenant_id" not in doc

    listed = env.client.get(
        f"{CASES}/{case_id}/documents", headers=headers(env.app, "auditor", tenant)
    ).json()
    assert [d["id"] for d in listed] == [doc["id"]]

    got = env.client.get(
        f"{CASES}/{case_id}/documents/{doc['id']}/content",
        headers=headers(env.app, "research_analyst", tenant),
    )
    assert got.status_code == 200
    assert got.content == PDF_BYTES
    assert got.headers["content-type"] == "application/octet-stream"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert got.headers["cache-control"] == "no-store"
    assert got.headers["content-disposition"].startswith(
        "attachment; filename*=UTF-8''statement.pdf"
    )


def test_stored_under_a_random_key_never_the_users_filename(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    upload(env, tenant, case_id, name="Secret Customer Q3 results.pdf")
    (key,) = env.storage.objects
    assert "Secret" not in key and ".pdf" not in key
    assert key.startswith(f"{tenant}/")


def test_all_allowed_categories_and_office_types(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    for category in ("financial_statement", "credit_report", "supporting"):
        assert upload(env, tenant, case_id, category=category).status_code == 201
    assert upload(env, tenant, case_id, office_zip("xlsx"), "figures.xlsx").status_code == 201
    assert upload(env, tenant, case_id, b"a,b\n1,2\n", "figures.csv").status_code == 201


def test_unsafe_filename_is_cleaned(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    doc = upload(env, tenant, case_id, name="..\\..\\evil name.pdf").json()
    assert doc["filename"] == "evil name.pdf"


# --- rejections: nothing is ever saved -------------------------------------------------------


def stored_documents(env: Env, case_id: str) -> int:
    return env.service.store.count_for_case(uuid.UUID(case_id))


@pytest.mark.parametrize(
    ("data", "name", "status", "reason"),
    [
        (b"MZ\x90 program", "tool.exe", 415, "unsupported_type"),
        (PDF_BYTES, "statement.png", 415, "extension_mismatch"),
        (b"", "empty.pdf", 422, "empty"),
        (zip_bomb(), "report.docx", 422, "zip_bomb"),
        (office_zip("docx", {"word/vbaProject.bin": b"m"}), "report.docx", 422, "macros"),
        (PDF_BYTES + b"/JavaScript", "statement.pdf", 422, "pdf_active_content"),
    ],
    ids=["exe", "mismatch", "empty", "zip_bomb", "macros", "pdf_js"],
)
def test_bad_files_are_refused_and_audited_without_the_filename(
    env: Env, tenant: str, data: bytes, name: str, status: int, reason: str
) -> None:
    case_id = new_case(env, tenant)
    response = upload(env, tenant, case_id, data, name)
    assert response.status_code == status
    assert response.json()["error"]["message"]
    assert stored_documents(env, case_id) == 0 and env.storage.objects == {}
    rejected = [e for e in audit(env.app, tenant) if e.action == "document.rejected"]
    assert [e.details for e in rejected] == [{"reason": reason}]
    assert name not in str([e for e in audit(env.app, tenant)])


def test_oversize_file_is_refused(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    response = upload(env, tenant, case_id, PDF_BYTES + b"x" * (1024 * 1024))  # limit is 1 MB here
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert stored_documents(env, case_id) == 0 and env.storage.objects == {}


def test_declared_size_is_checked_before_the_body_is_read(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    response = env.client.post(
        f"{CASES}/{case_id}/documents",
        content=b"x",
        headers={
            **headers(env.app, "underwriter", tenant),
            "content-length": str(500 * 1024 * 1024),
            "content-type": "multipart/form-data; boundary=x",
        },
    )
    assert response.status_code == 413


def test_an_infected_file_is_rejected_and_never_stored(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    response = upload(env, tenant, case_id, EICAR, "note.txt")
    assert response.status_code == 422
    assert "virus scan" in response.json()["error"]["message"]
    assert "Test-Signature" not in response.text  # the signature name stays out of the response
    assert stored_documents(env, case_id) == 0 and env.storage.objects == {}
    reasons = [e.details for e in audit(env.app, tenant) if e.action == "document.rejected"]
    assert reasons == [{"reason": "infected"}]


def test_if_the_scanner_is_down_nothing_is_accepted(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    env.scanner.down = True
    response = upload(env, tenant, case_id)
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "service_unavailable" and error["retryable"] is True
    assert "Nothing was saved" in error["message"]
    assert stored_documents(env, case_id) == 0 and env.storage.objects == {}
    assert env.scanner.scanned == 1  # it tried; it did not skip scanning


def test_if_storage_fails_nothing_is_recorded(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    env.storage.fail_put = True
    response = upload(env, tenant, case_id)
    assert response.status_code == 503
    assert stored_documents(env, case_id) == 0


def test_if_recording_fails_the_stored_object_is_removed(
    env: Env, tenant: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_id = new_case(env, tenant)

    def boom(**_: Any) -> None:
        raise RuntimeError("database down")

    monkeypatch.setattr(env.service.store, "add", boom)
    client = TestClient(env.app, raise_server_exceptions=False)
    response = client.post(
        f"{CASES}/{case_id}/documents",
        files={"file": ("statement.pdf", PDF_BYTES, "application/pdf")},
        data={"category": "supporting"},
        headers=headers(env.app, "underwriter", tenant),
    )
    assert response.status_code == 500
    assert env.storage.objects == {} and len(env.storage.deleted) == 1  # no orphan left behind


def test_a_case_holds_a_limited_number_of_documents(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    for _ in range(MAX_DOCUMENTS_PER_CASE):
        assert upload(env, tenant, case_id).status_code == 201
    assert upload(env, tenant, case_id).status_code == 409


def test_category_must_be_one_of_the_allowed_values(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    assert upload(env, tenant, case_id, category="bank_secrets").status_code == 422


def test_uploading_to_an_unknown_case_is_404(env: Env, tenant: str) -> None:
    assert upload(env, tenant, str(uuid.uuid4())).status_code == 404
    assert env.storage.objects == {}


# --- permissions and tenant isolation (AC-10) ------------------------------------------------


@pytest.mark.parametrize("role", ["research_analyst", "auditor", "administrator", "service"])
def test_only_case_writers_can_upload(env: Env, tenant: str, role: str) -> None:
    case_id = new_case(env, tenant)
    assert upload(env, tenant, case_id, role=role).status_code == 403
    assert env.storage.objects == {}


@pytest.mark.parametrize("role", ["administrator", "service"])
def test_roles_without_case_read_cannot_list_or_download(env: Env, tenant: str, role: str) -> None:
    case_id = new_case(env, tenant)
    doc = upload(env, tenant, case_id).json()
    h = headers(env.app, role, tenant)
    assert env.client.get(f"{CASES}/{case_id}/documents", headers=h).status_code == 403
    url = f"{CASES}/{case_id}/documents/{doc['id']}/content"
    assert env.client.get(url, headers=h).status_code == 403


def test_unauthenticated_requests_are_refused(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    assert env.client.get(f"{CASES}/{case_id}/documents").status_code == 401
    assert env.client.post(f"{CASES}/{case_id}/documents").status_code == 401


def test_another_tenant_cannot_upload_list_or_download(env: Env, tenant: str) -> None:
    other = f"{tenant}-other"
    case_id = new_case(env, tenant)
    doc = upload(env, tenant, case_id, name="Secret Name.pdf").json()
    intruder = headers(env.app, "underwriter", other)

    assert upload(env, other, case_id).status_code == 404
    assert env.client.get(f"{CASES}/{case_id}/documents", headers=intruder).status_code == 404
    url = f"{CASES}/{case_id}/documents/{doc['id']}/content"
    assert env.client.get(url, headers=intruder).status_code == 404
    assert len(env.storage.objects) == 1  # the intruder's upload stored nothing

    events = audit(env.app, other)
    assert [e.action for e in events] == ["authz.cross_tenant_denied"] * 3
    assert "Secret Name" not in str(events)


def test_a_document_cannot_be_fetched_through_a_different_case(env: Env, tenant: str) -> None:
    case_a, case_b = new_case(env, tenant), new_case(env, tenant)
    doc = upload(env, tenant, case_a).json()
    h = headers(env.app, "reviewer", tenant)
    assert (
        env.client.get(f"{CASES}/{case_b}/documents/{doc['id']}/content", headers=h).status_code
        == 404
    )
    assert (
        env.client.get(f"{CASES}/{case_a}/documents/{uuid.uuid4()}/content", headers=h).status_code
        == 404
    )


def test_storage_error_on_download_is_reported_without_internals(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    doc = upload(env, tenant, case_id).json()
    env.storage.fail_get = True
    client = TestClient(env.app, raise_server_exceptions=False)
    response = client.get(
        f"{CASES}/{case_id}/documents/{doc['id']}/content",
        headers=headers(env.app, "underwriter", tenant),
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "StorageUnavailable" not in response.text


# --- audit and immutability ------------------------------------------------------------------


def test_upload_and_download_are_audited_without_names_or_content(env: Env, tenant: str) -> None:
    case_id = new_case(env, tenant)
    doc = upload(env, tenant, case_id, name="Confidential Customer Report.pdf").json()
    env.client.get(
        f"{CASES}/{case_id}/documents/{doc['id']}/content",
        headers=headers(env.app, "underwriter", tenant),
    )
    events = list(reversed(audit(env.app, tenant)))
    assert [e.action for e in events] == [
        "case.created",
        "document.uploaded",
        "document.downloaded",
    ]
    assert events[1].details == {"document_id": doc["id"], "category": "financial_statement"}
    text = str(events)
    assert "Confidential" not in text and "%PDF" not in text


def test_document_records_cannot_be_edited_or_deleted_in_the_database(
    env: Env, tenant: str
) -> None:
    case_id = new_case(env, tenant)
    upload(env, tenant, case_id)
    engine = env.service.store._engine
    for statement in (
        "UPDATE case_documents SET original_filename = 'tampered'",
        "DELETE FROM case_documents",
        "TRUNCATE case_documents",
    ):
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
            conn.execute(sa.text(statement))
    with engine.connect() as conn:
        count = conn.execute(sa.select(sa.func.count()).select_from(case_documents)).scalar()
    assert (count or 0) >= 1


# --- switched off when not configured --------------------------------------------------------


def test_uploads_answer_503_when_storage_is_not_configured(
    database_url: str, db_app: FastAPI, tenant: str
) -> None:
    app = create_app(
        Settings(app_env=AppEnv.TEST, auth_mode=AuthMode.STUB, database_url=database_url)
    )
    client = TestClient(app)
    case = make_case(client, app, tenant)
    response = client.post(
        f"{CASES}/{case['id']}/documents",
        files={"file": ("statement.pdf", PDF_BYTES, "application/pdf")},
        data={"category": "supporting"},
        headers=headers(app, "underwriter", tenant),
    )
    assert response.status_code == 503
    assert "not set up" in response.json()["error"]["message"]
