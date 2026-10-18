"""Public-registry connectors with a fake fetcher and in-memory storage: no network in tests."""

import hashlib
import json
import uuid
from collections.abc import Iterator
from typing import BinaryIO

import pytest

from app.documents.storage import StorageUnavailableError
from app.research.connectors import (
    ConnectorRequest,
    PermanentConnectorError,
    RetryableConnectorError,
)
from app.research.fetch import Fetched, HttpsFetcher
from app.research.plan import Category
from app.research.public_connectors import GleifConnector, SecEdgarConnector, normalise_name
from app.research.snapshots import SnapshotStore

CASE = uuid.uuid4()
TICKERS = {
    "0": {"cik_str": 320187, "ticker": "NKE", "title": "NIKE, Inc."},
    "1": {"cik_str": 1, "ticker": "NKX", "title": "Nike Exploration Corp"},
    "2": {"cik_str": 2, "ticker": "TWIN", "title": "Twin Co"},
    "3": {"cik_str": 3, "ticker": "TWN", "title": "TWIN Company"},
}


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, file: BinaryIO, size: int) -> None:
        self.objects[key] = file.read()

    def get(self, key: str) -> Iterator[bytes]:
        if key not in self.objects:
            raise StorageUnavailableError
        yield self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class FakeFetcher:
    def __init__(self, routes: dict[str, bytes | Exception]) -> None:
        self.routes = routes
        self.urls: list[str] = []

    def get(
        self,
        url: str,
        *,
        allowed_hosts: frozenset[str],
        redirect_hosts: frozenset[str] = frozenset(),
    ) -> Fetched:
        self.urls.append(url)
        for prefix, result in self.routes.items():
            if url.startswith(prefix):
                if isinstance(result, Exception):
                    raise result
                return Fetched(url, 200, result, "application/json")
        raise AssertionError(f"unexpected url {url}")


def request(name: str | None = "Nike, Inc.", reg: str | None = None) -> ConnectorRequest:
    return ConnectorRequest(
        case_id=CASE,
        tenant_id="t1",
        category=Category.FINANCIALS,
        source_key="sec-edgar",
        jurisdictions=["US"],
        legal_name=name,
        registration_number=reg,
    )


def sec(
    extra: dict[str, bytes | Exception] | None = None,
) -> tuple[SecEdgarConnector, MemoryStorage, FakeFetcher]:
    routes: dict[str, bytes | Exception] = {
        "https://www.sec.gov/files/company_tickers.json": json.dumps(TICKERS).encode(),
        "https://data.sec.gov/submissions/CIK0000320187.json": b'{"filings": {"recent": {}}}',
        "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320187.json": b'{"facts": {"us-gaap": {}}}',
    }
    routes = {
        **(extra or {}),
        **{k: v for k, v in routes.items() if k not in (extra or {})},
    }  # overrides first
    storage, fetcher = MemoryStorage(), FakeFetcher(routes)
    return SecEdgarConnector(fetcher, SnapshotStore(storage)), storage, fetcher


def test_names_are_normalised_for_exact_matching() -> None:
    assert normalise_name("NIKE, Inc.") == normalise_name("nike inc") == "nike"
    assert normalise_name("The Twin Company") == normalise_name("TWIN Co") == "twin"


def test_sec_finds_the_company_and_saves_exact_snapshots_with_a_manifest() -> None:
    connector, storage, fetcher = sec()
    result = connector.execute(request())
    assert result.provenance_ref.startswith("snapshot://snapshots/t1/")
    ref, digest = result.provenance_ref.split("#sha256=")
    manifest_bytes = storage.objects[ref.removeprefix("snapshot://")]
    assert hashlib.sha256(manifest_bytes).hexdigest() == digest  # the ref proves the content
    manifest = json.loads(manifest_bytes)
    assert manifest["cik"] == "0000320187" and manifest["matched_on"] == "NIKE, Inc."
    assert [f["label"] for f in manifest["files"]] == ["submissions", "companyfacts"]
    for f in manifest["files"]:  # each stored file matches its recorded hash
        body = storage.objects[f["ref"].split("#")[0].removeprefix("snapshot://")]
        assert hashlib.sha256(body).hexdigest() == f["sha256"]
    assert len(storage.objects) == 3
    assert all(u.startswith("https://") for u in fetcher.urls)


def test_a_cik_in_the_registration_number_skips_the_name_search() -> None:
    connector, _, fetcher = sec()
    connector.execute(request(name=None, reg="CIK0000320187"))
    assert not any("company_tickers" in u for u in fetcher.urls)
    connector.execute(request(name="Whatever", reg="320187"))


@pytest.mark.parametrize("name", ["Twin Co", "Unknown Holdings"])
def test_no_unique_match_is_refused_never_guessed(name: str) -> None:
    connector, storage, _ = sec()
    with pytest.raises(PermanentConnectorError) as excinfo:
        connector.execute(request(name=name))
    assert excinfo.value.code == "no_unique_match"
    assert storage.objects == {}  # nothing saved, nothing claimed


def test_a_case_without_a_name_is_refused() -> None:
    connector, _, _ = sec()
    with pytest.raises(PermanentConnectorError) as excinfo:
        connector.execute(request(name=None))
    assert excinfo.value.code == "no_name"


def test_unreadable_registry_data_is_refused() -> None:
    connector, storage, _ = sec({"https://data.sec.gov/submissions/": b"<html>blocked</html>"})
    with pytest.raises(PermanentConnectorError) as excinfo:
        connector.execute(request())
    assert excinfo.value.code == "bad_response"
    assert storage.objects == {}  # a partial fetch leaves no manifest to point at


def test_temporary_registry_errors_stay_retryable() -> None:
    connector, _, _ = sec({"https://www.sec.gov/files": RetryableConnectorError("http_503")})
    with pytest.raises(RetryableConnectorError):
        connector.execute(request())


def gleif(body: bytes) -> tuple[GleifConnector, MemoryStorage, FakeFetcher]:
    storage = MemoryStorage()
    fetcher = FakeFetcher({"https://api.gleif.org/api/v1/lei-records": body})
    return GleifConnector(fetcher, SnapshotStore(storage)), storage, fetcher


def test_gleif_searches_by_exact_legal_name_and_snapshots_the_answer() -> None:
    body = json.dumps({"data": [{"id": "LEI1"}, {"id": "LEI2"}]}).encode()
    connector, storage, fetcher = gleif(body)
    result = connector.execute(request(name="NIKE, Inc."))
    assert result.items == 2
    assert "filter%5Bentity.legalName%5D=NIKE%2C+Inc." in fetcher.urls[0]
    assert next(iter(storage.objects.values())) == body  # byte-for-byte


def test_gleif_uses_the_lei_when_given_and_an_empty_answer_is_a_real_negative_result() -> None:
    connector, storage, fetcher = gleif(b'{"data": []}')
    result = connector.execute(request(name="x", reg="549300ABCDEFGHIJKL12"))
    assert "filter%5Blei%5D=549300ABCDEFGHIJKL12" in fetcher.urls[0]
    assert result.items == 0 and result.provenance_ref  # searched, found nothing, still logged
    assert len(storage.objects) == 1


def test_gleif_refuses_unexpected_shapes_and_missing_names() -> None:
    connector, storage, _ = gleif(b'{"errors": []}')
    with pytest.raises(PermanentConnectorError):
        connector.execute(request())
    assert storage.objects == {}
    with pytest.raises(PermanentConnectorError):
        connector.execute(request(name=None))


# --- the fetcher's guard rails (no network is touched) ------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://data.sec.gov/x",  # not https
        "https://evil.example/x",  # not on the allow-list
        "https://data.sec.gov.evil.example/x",  # look-alike host
        "file:///etc/passwd",
    ],
)
def test_fetcher_refuses_anything_off_the_allow_list(url: str) -> None:
    fetcher = HttpsFetcher("test@example.org")
    with pytest.raises(PermanentConnectorError) as excinfo:
        fetcher.get(url, allowed_hosts=frozenset({"data.sec.gov"}))
    assert excinfo.value.code == "host_not_allowed"


SUBMISSIONS_WITH_10K = json.dumps(
    {
        "filings": {
            "recent": {
                "form": ["8-K", "10-K", "10-K"],
                "accessionNumber": [
                    "0000320187-26-000090",
                    "0000320187-25-000073",
                    "0000320187-26-000088",
                ],
                "primaryDocument": ["a8k.htm", "nke-20250531.htm", "nke-20260531.htm"],
                "filingDate": ["2026-08-01", "2025-07-18", "2026-07-17"],
                "reportDate": ["2026-08-01", "2025-05-31", "2026-05-31"],
            }
        }
    }
).encode()
DOC_URL = "https://www.sec.gov/Archives/edgar/data/320187/000032018726000088/nke-20260531.htm"


def test_sec_also_keeps_the_newest_10k_text_with_its_hash() -> None:
    connector, storage, fetcher = sec(
        {
            "https://data.sec.gov/submissions/CIK0000320187.json": SUBMISSIONS_WITH_10K,
            DOC_URL: b"<html>the printed annual report</html>",
        }
    )
    manifest = json.loads(
        storage.objects[
            connector.execute(request()).provenance_ref.split("#")[0].removeprefix("snapshot://")
        ]
    )
    assert [f["label"] for f in manifest["files"]] == [
        "submissions",
        "companyfacts",
        "annual_report",
    ]
    report = next(f for f in manifest["files"] if f["label"] == "annual_report")
    assert report["url"] == DOC_URL
    body = storage.objects[report["ref"].split("#")[0].removeprefix("snapshot://")]
    assert body == b"<html>the printed annual report</html>"
    assert hashlib.sha256(body).hexdigest() == report["sha256"]
    assert manifest["annual_report"]["status"] == "RETRIEVED"
    assert (
        manifest["annual_report"]["accession"] == "0000320187-26-000088"
    )  # the newest, not the 8-K or 2025
    assert DOC_URL in fetcher.urls


def test_a_missing_10k_never_fails_the_retrieval_and_is_recorded() -> None:
    connector, storage, _ = sec()  # the filing list has no 10-K
    manifest = json.loads(
        storage.objects[
            connector.execute(request()).provenance_ref.split("#")[0].removeprefix("snapshot://")
        ]
    )
    assert [f["label"] for f in manifest["files"]] == ["submissions", "companyfacts"]
    assert manifest["annual_report"]["status"] == "NOT_FOUND"


def test_a_failed_10k_download_is_recorded_but_the_figures_are_still_kept() -> None:
    connector, storage, _ = sec(
        {
            "https://data.sec.gov/submissions/CIK0000320187.json": SUBMISSIONS_WITH_10K,
            DOC_URL: PermanentConnectorError("http_404"),
        }
    )
    manifest = json.loads(
        storage.objects[
            connector.execute(request()).provenance_ref.split("#")[0].removeprefix("snapshot://")
        ]
    )
    assert [f["label"] for f in manifest["files"]] == ["submissions", "companyfacts"]
    assert manifest["annual_report"]["status"] == "NOT_RETRIEVED"
    assert manifest["annual_report"]["accession"] == "0000320187-26-000088"


def test_an_odd_document_name_in_the_filing_list_is_never_turned_into_an_address() -> None:
    from app.research.public_connectors import latest_annual_report

    odd = {
        "filings": {
            "recent": {
                "form": ["10-K", "10-K", "10-K"],
                "accessionNumber": [
                    "0000320187-26-000088",
                    "not-an-accession",
                    "0000320187-26-000089",
                ],
                "primaryDocument": ["../../etc/passwd", "ok.htm", "evil.exe"],
                "filingDate": ["2026-07-17", "2026-07-18", "2026-07-19"],
                "reportDate": ["", "", ""],
            }
        }
    }
    assert latest_annual_report(odd, "0000320187") is None
    assert latest_annual_report({}, "0000320187") is None
