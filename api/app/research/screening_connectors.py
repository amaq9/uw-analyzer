"""Connectors for adverse-information and country context, again free, keyless and public.

    ofac-sdn    U.S. Treasury OFAC sanctions list (SDN names and aliases). Name screening only.
    world-bank  World Bank macro indicators (GDP growth, inflation, unemployment) per country.
    gdelt-news  GDELT news index: leads only. Discovery-only: never verifies a claim by itself.

Every connector keeps the material it received as snapshots. Results say exactly what was searched
and how, including limits (a name search is not a compliance screening). A search that finds nothing
is a real, logged negative result."""

import csv
import io
import json
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote, urlencode

from app.research.connectors import (
    ConnectorRequest,
    ConnectorResult,
    PermanentConnectorError,
    RetryableConnectorError,
)
from app.research.fetch import Fetcher
from app.research.plan import Category
from app.research.public_connectors import _json, _now, normalise_name
from app.research.snapshots import SnapshotStore

MAX_LISTED = 25


def _tokens(name: str) -> frozenset[str]:
    return frozenset(normalise_name(name).split())


class OfacSdnConnector:
    key = "ofac-sdn"
    version = "1"
    _HOSTS = frozenset({"sanctionslistservice.ofac.treas.gov"})
    _FILE_HOSTS = frozenset({"wc2h-sls-prod-public-published.s3.us-gov-west-1.amazonaws.com"})
    _BASE = "https://sanctionslistservice.ofac.treas.gov/api/publicationpreview/exports/"

    def __init__(self, fetcher: Fetcher, snapshots: SnapshotStore) -> None:
        self._fetcher = fetcher
        self._snapshots = snapshots

    def describe(self, request: ConnectorRequest) -> str:
        return (
            "Screen the legal name against the OFAC SDN list and its aliases (name match only; "
            "not a compliance screening)"
        )

    def _list(self, request: ConnectorRequest, name: str) -> tuple[list[list[str]], dict[str, Any]]:
        got = self._fetcher.get(
            self._BASE + name, allowed_hosts=self._HOSTS, redirect_hosts=self._FILE_HOSTS
        )
        snap = self._snapshots.save(request.tenant_id, request.case_id, got.body)
        try:
            rows = list(csv.reader(io.StringIO(got.body.decode("latin-1"))))
        except csv.Error:
            raise PermanentConnectorError("bad_response", "Unreadable list.") from None
        if len(rows) < 100:  # the real list has thousands of entries
            raise PermanentConnectorError("bad_response", "The list looks incomplete.")
        return rows, {"file": name, "ref": snap.ref, "sha256": snap.sha256, "bytes": snap.size}

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        if not request.legal_name:
            raise PermanentConnectorError("no_name", "The case has no legal name to screen.")
        sdn, sdn_file = self._list(request, "sdn.csv")
        alt, alt_file = self._list(request, "alt.csv")
        searched = _tokens(request.legal_name)
        if not searched:
            raise PermanentConnectorError("no_name", "The name has no searchable words.")

        candidates: dict[str, tuple[str, str, str]] = {}  # ent_num -> (name, type, program)
        names: list[tuple[str, str, str]] = []  # (ent_num, name, matched_on)
        for row in sdn:
            if len(row) >= 4:
                candidates[row[0].strip()] = (row[1], row[2].strip(), row[3].strip())
                names.append((row[0].strip(), row[1], "name"))
        for row in alt:
            if len(row) >= 4:
                names.append((row[0].strip(), row[3], "alias"))

        exact: dict[str, dict[str, str]] = {}
        possible: dict[str, dict[str, str]] = {}
        for ent, candidate, matched_on in names:
            tokens = _tokens(candidate)
            if not tokens:
                continue
            info = candidates.get(ent, ("", "", ""))
            entry = {
                "entity_number": ent,
                "listed_name": info[0],
                "type": info[1],
                "program": info[2],
                "matched_name": candidate,
                "matched_on": matched_on,
            }
            if tokens == searched:
                exact.setdefault(ent, entry)
            elif (
                len(searched) >= 2
                and len(tokens) >= 2
                and (searched <= tokens or tokens <= searched)
            ):
                possible.setdefault(ent, entry)
        result = {
            "source": self.key,
            "connector_version": self.version,
            "retrieved_at": _now(),
            "searched_name": request.legal_name,
            "normalised_words": sorted(searched),
            "files": [sdn_file, alt_file],
            "exact_match_count": len(exact),
            "possible_match_count": len(possible),
            "exact_matches": list(exact.values())[:MAX_LISTED],
            "possible_matches": [p for e, p in possible.items() if e not in exact][:MAX_LISTED],
            "method": "Exact match on the normalised words of the name or an alias; possible "
            "matches share all words of the shorter name (two or more words). Corporate "
            "suffixes such as Inc. and Ltd. are ignored.",
            "limitations": "Name search only. It does not use addresses or identifiers, does not "
            "cover other sanctions lists (UN, EU, Canada), and is not a compliance screening. "
            "Any match must be reviewed by a person.",
        }
        snap = self._snapshots.save(
            request.tenant_id, request.case_id, json.dumps(result, indent=2).encode()
        )
        return ConnectorResult(provenance_ref=snap.ref, items=len(exact) + len(possible))


class WorldBankConnector:
    key = "world-bank"
    version = "1"
    _HOSTS = frozenset({"api.worldbank.org"})
    INDICATORS = {
        "NY.GDP.MKTP.KD.ZG": "GDP growth (annual %)",
        "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
        "SL.UEM.TOTL.ZS": "Unemployment (% of labour force)",
    }
    MAX_COUNTRIES = 5

    def __init__(self, fetcher: Fetcher, snapshots: SnapshotStore) -> None:
        self._fetcher = fetcher
        self._snapshots = snapshots

    def describe(self, request: ConnectorRequest) -> str:
        return "Retrieve World Bank GDP growth, inflation and unemployment for the named countries"

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        countries = [c for c in request.jurisdictions if c != "GLOBAL"][: self.MAX_COUNTRIES]
        if not countries:
            raise PermanentConnectorError("no_country", "No country was named for this run.")
        responses = []
        for country in countries:
            for indicator in self.INDICATORS:
                url = (
                    f"https://api.worldbank.org/v2/country/{quote(country)}/indicator/{indicator}"
                    "?format=json&mrv=5"
                )
                got = self._fetcher.get(url, allowed_hosts=self._HOSTS)
                data = _json(got.body)
                if not (isinstance(data, list) and len(data) == 2):
                    raise PermanentConnectorError(
                        "bad_response", f"No data returned for {country} {indicator}."
                    )
                responses.append(
                    {"country": country, "indicator": indicator, "url": url, "body": data}
                )
        bundle = {
            "source": self.key,
            "connector_version": self.version,
            "retrieved_at": _now(),
            "indicators": self.INDICATORS,
            "responses": responses,
            "limitations": "Country-level macro indicators only. They are not a sector outlook.",
        }
        snap = self._snapshots.save(
            request.tenant_id, request.case_id, json.dumps(bundle, indent=2).encode()
        )
        return ConnectorResult(provenance_ref=snap.ref, items=len(responses))


class GdeltNewsConnector:
    """Leads from news coverage. The index allows one request every five seconds, so the call waits
    first; a refusal is retried by the executor with backoff."""

    key = "gdelt-news"
    version = "1"
    _HOSTS = frozenset({"api.gdeltproject.org"})
    ADVERSE_TERMS = (
        "lawsuit OR fraud OR bankruptcy OR insolvency OR sanctions OR investigation OR default "
        'OR recall OR "class action" OR "going concern"'
    )
    SECTOR_TERMS = "outlook OR forecast OR demand OR downturn OR slowdown OR growth"

    def __init__(
        self,
        fetcher: Fetcher,
        snapshots: SnapshotStore,
        pause: Callable[[float], None] = time.sleep,
    ) -> None:
        self._fetcher = fetcher
        self._snapshots = snapshots
        self._pause = pause

    def describe(self, request: ConnectorRequest) -> str:
        if request.category is Category.COUNTRY_INDUSTRY:
            return "Search recent news for the industry's outlook (leads only, discovery-only)"
        return (
            "Search recent news for adverse stories about the company (leads only, discovery-only)"
        )

    def _query(self, request: ConnectorRequest) -> str:
        if request.category is Category.COUNTRY_INDUSTRY:
            if not request.industry:
                raise PermanentConnectorError("no_industry", "The case has no industry.")
            return f'"{request.industry}" ({self.SECTOR_TERMS})'
        if not request.legal_name:
            raise PermanentConnectorError("no_name", "The case has no legal name.")
        words = [
            w
            for w in request.legal_name.replace(",", " ").split()
            if w.lower().strip(".")
            not in {
                "inc",
                "incorporated",
                "corp",
                "corporation",
                "ltd",
                "limited",
                "llc",
                "plc",
                "co",
            }
        ]
        if not words:
            raise PermanentConnectorError("no_name", "The name has no searchable words.")
        return f'"{" ".join(words)}" ({self.ADVERSE_TERMS})'

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        query = self._query(request)
        self._pause(6.0)
        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": "50",
            "format": "json",
            "timespan": "12months",
            "sort": "hybridrel",
        }
        url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urlencode(params)
        got = self._fetcher.get(url, allowed_hosts=self._HOSTS)
        text = got.body.decode("utf-8", errors="replace").strip()
        parsed: Any = None
        if text and not text.startswith(("{", "[")) and "limit requests" in text.lower():
            # The index answers a too-fast request with a plain-text note, not an HTTP error.
            raise RetryableConnectorError("rate_limited")
        if text:
            try:
                parsed = json.loads(text)
            except ValueError:
                raise PermanentConnectorError("bad_response", "Unreadable news response.") from None
        articles = (parsed or {}).get("articles", []) if isinstance(parsed, dict) else []
        record = {
            "source": self.key,
            "connector_version": self.version,
            "retrieved_at": _now(),
            "category": request.category.value,
            "query": query,
            "timespan": "12 months",
            "article_count": len(articles),
            "response": parsed,
            "limitations": "News index leads only (discovery-only). Titles and links must be "
            "opened and read from the publisher before anything is relied on. Name matches can "
            "be about a different organisation or a common word.",
        }
        snap = self._snapshots.save(
            request.tenant_id, request.case_id, json.dumps(record, indent=2).encode()
        )
        return ConnectorResult(provenance_ref=snap.ref, items=len(articles))
