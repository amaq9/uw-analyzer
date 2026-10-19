"""Alpha Vantage market news and sentiment (ADR 0023). The first connector that needs a key.

    alpha-vantage-news  News feed for the company's listed share (adverse search) or for the
                        industry's market topic (country and industry). Discovery-only: titles
                        and links are leads, never verification by themselves.

The key comes from the environment (ALPHA_VANTAGE_API_KEY) and is only ever put in the request
address. It is never saved: snapshots hold the provider's response, and the addresses recorded in
them have the key removed. Searching sends the company name and share symbol to Alpha Vantage."""

import json
import re
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

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

_BASE = "https://www.alphavantage.co/query?"
# A share-class label after the company name, e.g. "Nike Inc - Class B" or "Acme Corp Common Stock".
_SHARE_CLASS = re.compile(
    r"\s*-?\s*\b(?:(?:class|cl|series)\s+[a-z0-9]|common stock|common shares|ordinary shares)\b.*$",
    re.IGNORECASE,
)

# Alpha Vantage's own region names for the jurisdictions a person can name. Used only to choose
# between listings of the SAME exact company name (e.g. a U.S. share and a Frankfurt copy).
_REGIONS = {
    "US": {"United States"},
    "GB": {"United Kingdom"},
    "CA": {"Toronto", "Toronto Venture"},
    "DE": {"Frankfurt", "XETRA"},
}

# Industry words -> the provider's fixed topic list. Anything else is not guessed.
TOPICS = (
    ("technology", ("technology", "software", "semiconductor", "internet", "telecom")),
    ("retail_wholesale", ("retail", "wholesale", "apparel", "footwear", "consumer")),
    ("manufacturing", ("manufactur", "industrial", "machinery", "automotive", "chemical")),
    (
        "energy_transportation",
        ("energy", "oil", "gas", "utilit", "transport", "logistic", "shipping", "airline"),
    ),
    ("life_sciences", ("pharma", "biotech", "health", "medical")),
    ("real_estate", ("real estate", "construction", "property")),
    ("finance", ("bank", "insurance", "financ")),
)
NEGATIVE_LABELS = frozenset({"Bearish", "Somewhat-Bearish"})


def listing_name(name: str) -> str:
    """The company part of a listing's name, normalised like a case's legal name."""
    return normalise_name(_SHARE_CLASS.sub("", name))


def topic_for(industry: str) -> str | None:
    text = industry.lower()
    for topic, words in TOPICS:
        if any(w in text for w in words):
            return topic
    return None


class AlphaVantageNewsConnector:
    key = "alpha-vantage-news"
    version = "1"
    _HOSTS = frozenset({"www.alphavantage.co"})
    LIMIT = 50
    PAUSE_SECONDS = 1.5  # the provider refuses bursts faster than about one request a second

    def __init__(
        self,
        fetcher: Fetcher,
        snapshots: SnapshotStore,
        api_key: str,
        pause: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key.strip():
            raise ValueError("An Alpha Vantage key is required.")
        self._fetcher = fetcher
        self._snapshots = snapshots
        self._api_key = api_key.strip()
        self._pause = pause

    def describe(self, request: ConnectorRequest) -> str:
        if request.category is Category.COUNTRY_INDUSTRY:
            return (
                "Retrieve recent Alpha Vantage market news for the industry's topic "
                "(leads only, discovery-only)"
            )
        return (
            "Find the company's listed share on Alpha Vantage (exact name) and retrieve recent "
            "news about it with the provider's sentiment labels (leads only, discovery-only)"
        )

    def _call(self, params: dict[str, str]) -> tuple[dict[str, Any], bytes, str]:
        """One request: the parsed answer, the exact bytes and the address WITHOUT the key."""
        shown = _BASE + urlencode(params)
        self._pause(self.PAUSE_SECONDS)
        got = self._fetcher.get(
            _BASE + urlencode({**params, "apikey": self._api_key}), allowed_hosts=self._HOSTS
        )
        data = _json(got.body)
        if not isinstance(data, dict):
            raise PermanentConnectorError("bad_response", "Unexpected provider response.")
        # The provider answers 200 with a message instead of data when it refuses a request.
        if "Error Message" in data:
            raise PermanentConnectorError("bad_request", "The provider rejected the request.")
        notice = str(data.get("Information") or data.get("Note") or "")
        if notice:
            lowered = notice.lower()
            if "rate limit" in lowered or "per day" in lowered or "per minute" in lowered:
                raise RetryableConnectorError("rate_limited")
            if "apikey" in lowered or "api key" in lowered:
                raise PermanentConnectorError("key_refused", "The provider refused the key.")
            if "premium" in lowered:
                raise PermanentConnectorError(
                    "premium_required", "This key's plan does not include the endpoint."
                )
            raise PermanentConnectorError("refused", "The provider refused the request.")
        return data, got.body, shown

    def _find_symbol(self, request: ConnectorRequest) -> tuple[str, dict[str, Any]]:
        if not request.legal_name:
            raise PermanentConnectorError("no_name", "The case has no legal name to look up.")
        wanted = normalise_name(request.legal_name)
        if not wanted:
            raise PermanentConnectorError("no_name", "The name has no searchable words.")
        data, body, shown = self._call({"function": "SYMBOL_SEARCH", "keywords": wanted})
        rows = data.get("bestMatches")
        if not isinstance(rows, list):
            raise PermanentConnectorError("bad_response", "Unexpected symbol search response.")
        exact = [
            r
            for r in rows
            if isinstance(r, dict)
            and r.get("3. type") == "Equity"
            and listing_name(str(r.get("2. name", ""))) == wanted
        ]
        symbols = {str(r["1. symbol"]): r for r in exact if r.get("1. symbol")}
        if len(symbols) > 1:
            regions = set().union(*(_REGIONS.get(j, set()) for j in request.jurisdictions))
            symbols = {s: r for s, r in symbols.items() if r.get("4. region") in regions}
        if len(symbols) != 1:
            # Never guess between look-alike listings (P-03).
            raise PermanentConnectorError(
                "no_unique_match",
                f"{len(symbols)} listed shares match the exact name in the named countries.",
            )
        symbol, row = next(iter(symbols.items()))
        snap = self._snapshots.save(request.tenant_id, request.case_id, body)
        lookup = {
            "label": "symbol_search",
            "url": shown,
            "ref": snap.ref,
            "sha256": snap.sha256,
            "bytes": snap.size,
            "matched_symbol": symbol,
            "matched_name": str(row.get("2. name", "")),
            "region": str(row.get("4. region", "")),
        }
        return symbol, lookup

    def execute(self, request: ConnectorRequest) -> ConnectorResult:
        files: list[dict[str, Any]] = []
        if request.category is Category.COUNTRY_INDUSTRY:
            if not request.industry:
                raise PermanentConnectorError("no_industry", "The case has no industry.")
            topic = topic_for(request.industry)
            if topic is None:
                raise PermanentConnectorError(
                    "no_topic", "The industry does not map to one of the provider's news topics."
                )
            params = {"function": "NEWS_SENTIMENT", "topics": topic}
            searched: dict[str, str] = {"industry": request.industry, "topic": topic}
        else:
            symbol, lookup = self._find_symbol(request)
            files.append(lookup)
            params = {"function": "NEWS_SENTIMENT", "tickers": symbol}
            searched = {"legal_name": request.legal_name or "", "symbol": symbol}
        params |= {"sort": "LATEST", "limit": str(self.LIMIT)}
        data, body, shown = self._call(params)
        feed = data.get("feed")
        if not isinstance(feed, list):
            raise PermanentConnectorError("bad_response", "Unexpected news response.")
        snap = self._snapshots.save(request.tenant_id, request.case_id, body)
        files.append(
            {
                "label": "news",
                "url": shown,
                "ref": snap.ref,
                "sha256": snap.sha256,
                "bytes": snap.size,
            }
        )
        record: dict[str, Any] = {
            "source": self.key,
            "connector_version": self.version,
            "retrieved_at": _now(),
            "category": request.category.value,
            "searched": searched,
            "article_count": len(feed),
            "files": files,
            "limitations": "Market news leads only (discovery-only). Titles and links must be "
            "opened and read from the publisher before anything is relied on. Sentiment labels "
            "are the provider's own automated scores, not a finding. The feed is the latest "
            f"{self.LIMIT} articles, not a full search.",
        }
        if "symbol" in searched:
            record["provider_negative_label_count"] = sum(
                1
                for article in feed
                if isinstance(article, dict)
                for t in article.get("ticker_sentiment") or []
                if isinstance(t, dict)
                and t.get("ticker") == searched["symbol"]
                and t.get("ticker_sentiment_label") in NEGATIVE_LABELS
            )
        manifest = self._snapshots.save(
            request.tenant_id, request.case_id, json.dumps(record, indent=2).encode()
        )
        return ConnectorResult(provenance_ref=manifest.ref, items=len(feed))
