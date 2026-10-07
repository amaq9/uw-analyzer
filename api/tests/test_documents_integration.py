"""The real thing: S3 object storage and the ClamAV scanner (including the EICAR test file).

Set TEST_S3_ENDPOINT_URL, TEST_S3_ACCESS_KEY, TEST_S3_SECRET_KEY and TEST_CLAMAV_HOST (see
docs/runbooks/local-development.md). Locally these tests skip when unset; in CI they must run.
"""

import io
import os
import uuid
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.config import AppEnv, AuthMode, Settings
from app.documents.scanner import ClamAVScanner
from app.documents.storage import S3Storage, StorageUnavailableError
from app.main import create_app
from tests.files import EICAR, PDF_BYTES
from tests.test_cases_api import CASES, audit, headers, make_case

BUCKET = "uw-documents-test"


def _need(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        if os.environ.get("CI"):
            pytest.fail(f"{name} must be set in CI")
        pytest.skip(f"{name} not set; skipping S3/ClamAV integration tests")
    return value


@pytest.fixture(scope="module")
def storage() -> S3Storage:
    store = S3Storage(
        endpoint_url=_need("TEST_S3_ENDPOINT_URL"),
        bucket=BUCKET,
        access_key=_need("TEST_S3_ACCESS_KEY"),
        secret_key=_need("TEST_S3_SECRET_KEY"),
    )
    store.ensure_bucket()
    return store


@pytest.fixture(scope="module")
def scanner() -> ClamAVScanner:
    return ClamAVScanner(_need("TEST_CLAMAV_HOST"), int(os.environ.get("TEST_CLAMAV_PORT", "3310")))


@pytest.fixture
def real_app(
    database_url: str, db_app: FastAPI, storage: S3Storage, scanner: ClamAVScanner
) -> Iterator[FastAPI]:
    settings = Settings(
        app_env=AppEnv.TEST,
        auth_mode=AuthMode.STUB,
        database_url=database_url,
        s3_endpoint_url=_need("TEST_S3_ENDPOINT_URL"),
        s3_bucket=BUCKET,
        s3_access_key=SecretStr(_need("TEST_S3_ACCESS_KEY")),
        s3_secret_key=SecretStr(_need("TEST_S3_SECRET_KEY")),
        clamav_host=_need("TEST_CLAMAV_HOST"),
    )
    yield create_app(settings)


# --- storage ---------------------------------------------------------------------------------


def test_storage_round_trip_and_delete(storage: S3Storage) -> None:
    key = f"test/{uuid.uuid4().hex}"
    data = os.urandom(5 * 1024 * 1024 + 123)  # larger than one read chunk
    storage.put(key, io.BytesIO(data), len(data))
    assert b"".join(storage.get(key)) == data
    storage.delete(key)
    with pytest.raises(StorageUnavailableError):
        b"".join(storage.get(key))


def test_storage_errors_become_a_clean_exception(storage: S3Storage) -> None:
    dead = S3Storage(
        endpoint_url="http://127.0.0.1:1", bucket=BUCKET, access_key="x", secret_key="y"
    )
    with pytest.raises(StorageUnavailableError):
        dead.put("k", io.BytesIO(b"x"), 1)


# --- scanner ---------------------------------------------------------------------------------


def test_real_scanner_passes_a_clean_file(scanner: ClamAVScanner) -> None:
    assert scanner.scan(io.BytesIO(PDF_BYTES)).clean is True


def test_real_scanner_catches_the_eicar_test_virus(scanner: ClamAVScanner) -> None:
    result = scanner.scan(io.BytesIO(EICAR))
    assert result.clean is False
    assert result.signature and "Eicar" in result.signature


def test_real_scanner_handles_a_large_clean_file(scanner: ClamAVScanner) -> None:
    assert scanner.scan(io.BytesIO(b"\x00" * (10 * 1024 * 1024))).clean is True


# --- the whole pipeline, for real ------------------------------------------------------------


def test_clean_upload_is_stored_in_s3_and_downloads_identically(
    real_app: FastAPI, storage: S3Storage, tenant: str
) -> None:
    client = TestClient(real_app)
    case_id = str(make_case(client, real_app, tenant)["id"])
    response = client.post(
        f"{CASES}/{case_id}/documents",
        files={"file": ("statement.pdf", PDF_BYTES, "application/pdf")},
        data={"category": "financial_statement"},
        headers=headers(real_app, "underwriter", tenant),
    )
    assert response.status_code == 201, response.text
    doc = response.json()
    got = client.get(
        f"{CASES}/{case_id}/documents/{doc['id']}/content",
        headers=headers(real_app, "auditor", tenant),
    )
    assert got.content == PDF_BYTES
    # the object really is in the bucket, under a random key inside this tenant's prefix
    engine = sa.create_engine(os.environ["TEST_DATABASE_URL"])
    with engine.connect() as conn:
        key = conn.execute(
            sa.text("SELECT storage_key FROM case_documents WHERE id = :id"), {"id": doc["id"]}
        ).scalar_one()
    assert key.startswith(f"{tenant}/") and "statement" not in key


def test_eicar_upload_is_rejected_by_the_real_scanner_and_never_stored(
    real_app: FastAPI, storage: S3Storage, tenant: str
) -> None:
    client = TestClient(real_app)
    case_id = str(make_case(client, real_app, tenant)["id"])
    response = client.post(
        f"{CASES}/{case_id}/documents",
        files={"file": ("harmless-looking.txt", EICAR, "text/plain")},
        data={"category": "supporting"},
        headers=headers(real_app, "underwriter", tenant),
    )
    assert response.status_code == 422
    assert "virus scan" in response.json()["error"]["message"]
    rejected = [e.details for e in audit(real_app, tenant) if e.action == "document.rejected"]
    assert rejected == [{"reason": "infected"}]
    listed = client.get(
        f"{CASES}/{case_id}/documents", headers=headers(real_app, "reviewer", tenant)
    ).json()
    assert listed == []


# --- configuration ---------------------------------------------------------------------------


def _settings(**kw: object) -> Settings:
    base: dict[str, object] = {
        "app_env": AppEnv.TEST,
        "auth_mode": AuthMode.STUB,
        "database_url": "postgresql+psycopg://u:p@localhost/db",
    }
    return Settings(**{**base, **kw})  # type: ignore[arg-type]


def test_uploads_are_off_when_nothing_is_configured() -> None:
    assert _settings().documents_configured is False


def test_partial_document_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError, match="together"):
        _settings(s3_endpoint_url="http://localhost:8333", s3_bucket="b")


def test_full_document_configuration_is_accepted_and_secrets_are_hidden() -> None:
    settings = _settings(
        s3_endpoint_url="http://localhost:8333",
        s3_bucket="b",
        s3_access_key=SecretStr("ak"),
        s3_secret_key=SecretStr("sk"),
        clamav_host="localhost",
    )
    assert settings.documents_configured is True
    assert "sk" not in repr(settings) and "ak'" not in repr(settings)


def test_plain_http_storage_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="https"):
        Settings(
            app_env=AppEnv.PROD,
            database_url="postgresql+psycopg://u:p@localhost/db",
            oidc_issuer="https://idp.example/",
            oidc_audience="a",
            oidc_jwks_url="https://idp.example/jwks.json",
            s3_endpoint_url="http://s3.example",
            s3_bucket="b",
            s3_access_key=SecretStr("ak"),
            s3_secret_key=SecretStr("sk"),
            clamav_host="h",
        )


@pytest.mark.parametrize("mb", [0, 26])
def test_upload_limit_must_stay_below_the_scanner_limit(mb: int) -> None:
    with pytest.raises(ValidationError):
        _settings(max_upload_mb=mb)
