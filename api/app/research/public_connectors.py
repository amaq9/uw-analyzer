"""Real connectors to free public registries. Each reaches exactly one registry, saves the exact
response it received as a snapshot, and returns that snapshot as its provenance reference. They only
fetch: they do not interpret, summarise or decide anything. An empty answer from a registry is still
a real, logged search (a negative result), never a made-up one.

    sec-edgar  U.S. SEC filer index, filing list and reported financial data (official)
    gleif      Global LEI register: legal entity identity and ownership links (official)

Searching sends the company name to the registry. Use only with names you are willing to look up
publicly."""

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from app.research.connectors import (
    ConnectorRequest,
    ConnectorResult,
    PermanentConnectorError,
    RetryableConnectorError,
)
from app.research.fetch import Fetcher
from app.research.snapshots import SnapshotStore

_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "co", "company", "ltd", "limited", "llc",
    "plc", "lp", "sa", "ag", "nv", "the",
}  # fmt: skip
_CIK = re.compile(r"^(?:CIK)?0*(\d{1,10})$", re.IGNORECASE)
_LEI = re.compile(r"^[A-Z0-9]{18}[0-9]{2}$")


def normalise_name(name: str) -> str:
    words = re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()
    return " ".join(w for w in words if w not in _SUFFIXES)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(body: bytes) -> Any:
    try:
        return json.loads(body)
    except ValueError:
        raise PermanentConnectorError(
            "bad_response", "Registry returned unreadable data."
        ) from None


_ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_DOCUMENT = re.compile(r"^[A-Za-z0-9_.\-]+\.html?$")


def latest_annual_report(submissions: Any, cik: str) -> dict[str, str] | None:
    """The newest 10-K in the filing list: accession, main document, dates and public address."""
    recent = (submissions or {}).get("filings", {}).get("recent", {})
    forms, numbers = recent.get("form", []), recent.get("accessionNumber", [])
    documents, filed = recent.get("primaryDocument", []), recent.get("filingDate", [])
    periods = recent.get("reportDate", [])
    best: dict[str, str] | None = None
    for i, form in enumerate(forms):
        if form != "10-K" or i >= len(numbers) or i >= len(documents):
            continue
        accession, document = str(numbers[i]), str(documents[i])
        if not _ACCESSION.match(accession) or not _DOCUMENT.match(document):
            continue  # never build an address from something unexpected
        row = {
            "accession": accession,
            "document": document,
            "filed": str(filed[i]) if i < len(filed) else "",
            "period": str(periods[i]) if i < len(periods) else "",
            "url": (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                f"{accession.replace('-', '')}/{document}"
            ),
        }
        if best is None or row["filed"] > best["filed"]:
            best = row
    return best


class SecEdgarConnector:
    key = "sec-edgar"
    version = "2"
    _HOSTS = frozenset({"www.sec.gov", "data.sec.gov"})

    def __init__(self, fetcher: Fetcher, snapshots: SnapshotStore) -> None:
        self._fetcher = fetcher
        self._snapshots = snapshots

    def describe(self, request: ConnectorRequest) -> str:
        return (
            "Find the company in the SEC EDGAR filer index (exact name or CIK) and retrieve its "
            "filing list and reported financial data"
        )

    def _find_cik(self, request: ConnectorRequest) -> tuple[str, str]:
        if request.registration_number:
            m = _CIK.fullmatch(request.registration_number.strip())
            if m:
                return f"{int(m.group(1)):010d}", "registration number"
        if not request.legal_name:
            raise PermanentConnectorError("no_name", "The case has no legal name to look up.")
        index = _json(
            self._fetcher.get(
                "https://www.sec.gov/files/company_tickers.json", allowed_hosts=self._HOSTS
            ).body
        )
        wanted = normalise_name(request.legal_name)
        matches = {
            int(row["cik_str"]): str(row["title"])
            for row in index.values()
            if normalise_name(str(row["title"])) == wanted
        }
        if len(matches) != 1:
            # Never guess between look-alike companies (P-03): a person must supply the CIK.
            raise PermanentConnectorError(
                "no_unique_match",
                f"{len(matches)} SEC filers match the exact name; supply the CIK as the "
                "registration number.",
            )
        cik, title = next(iter(matches.items()))
        return f"{cik:010d}", title

    def _annual_report(
        self,
        request: ConnectorRequest,
        cik: str,
        submissions: Any,
        files: list[dict[str, Any]],
    ) -> dict[str, str]:
        """Also keep the printed 10-K (notes and auditor's report). It never fails the retrieval:
        the reported figures are the main result, so a miss is recorded and the analysis says so."""
        found = latest_annual_report(submissions, cik)
        if found is None:
            return {"status": "NOT_FOUND", "reason": "No 10-K was found in the filing list."}
        try:
            got = self._fetcher.get(found["url"], allowed_hosts=self._HOSTS)
        except (PermanentConnectorError, RetryableConnectorError) as exc:
            return {**found, "status": "NOT_RETRIEVED", "reason": str(exc)[:200]}
        snap = self._snapshots.save(request.tenant_id, request.case_id, got.body)
        files.append(
            {
                "label": "annual_report",
                "url": found["url"],
                "ref": snap.ref,
                "sha256": snap.sha256,
                "bytes": snap.size,
            }
        )
        return {**found, "status": "RETRIEVED"}

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        cik, matched = self._find_cik(request)
        files: list[dict[str, Any]] = []
        submissions: Any = None
        for label, url in (
            ("submissions", f"https://data.sec.gov/submissions/CIK{cik}.json"),
            ("companyfacts", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"),
        ):
            got = self._fetcher.get(url, allowed_hosts=self._HOSTS)
            parsed = _json(got.body)  # refuse anything that is not the JSON we expect
            if label == "submissions":
                submissions = parsed
            snap = self._snapshots.save(request.tenant_id, request.case_id, got.body)
            files.append(
                {
                    "label": label,
                    "url": url,
                    "ref": snap.ref,
                    "sha256": snap.sha256,
                    "bytes": snap.size,
                }
            )
        annual_report = self._annual_report(request, cik, submissions, files)
        manifest = {
            "source": self.key,
            "connector_version": self.version,
            "retrieved_at": _now(),
            "cik": cik,
            "matched_on": matched,
            "files": files,
            "annual_report": annual_report,
        }
        snap = self._snapshots.save(
            request.tenant_id, request.case_id, json.dumps(manifest, indent=2).encode()
        )
        return ConnectorResult(provenance_ref=snap.ref, items=len(files))


class GleifConnector:
    key = "gleif"
    version = "1"
    _HOSTS = frozenset({"api.gleif.org"})

    def __init__(self, fetcher: Fetcher, snapshots: SnapshotStore) -> None:
        self._fetcher = fetcher
        self._snapshots = snapshots

    def describe(self, request: ConnectorRequest) -> str:
        return "Search the Global LEI register for the legal entity (by LEI or exact legal name)"

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        reg = (request.registration_number or "").strip().upper()
        if _LEI.fullmatch(reg):
            params = {"filter[lei]": reg, "page[size]": "10"}
        elif request.legal_name:
            params = {"filter[entity.legalName]": request.legal_name, "page[size]": "10"}
        else:
            raise PermanentConnectorError("no_name", "The case has no legal name or LEI.")
        url = "https://api.gleif.org/api/v1/lei-records?" + urlencode(params)
        got = self._fetcher.get(url, allowed_hosts=self._HOSTS)
        data = _json(got.body)
        if not isinstance(data, dict) or "data" not in data:
            raise PermanentConnectorError("bad_response", "Unexpected register response.")
        snap = self._snapshots.save(request.tenant_id, request.case_id, got.body)
        return ConnectorResult(provenance_ref=snap.ref, items=len(data["data"]))
