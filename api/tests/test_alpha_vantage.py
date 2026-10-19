"""Alpha Vantage news connector with a fake fetcher: no network, and the key is never stored."""

import json
from typing import Any

import pytest

from app.research.alpha_vantage import AlphaVantageNewsConnector, listing_name, topic_for
from app.research.connectors import PermanentConnectorError, RetryableConnectorError
from app.research.fetch import Fetched
from app.research.plan import Category
from app.research.snapshots import SnapshotStore
from tests.test_public_connectors import MemoryStorage
from tests.test_screening_connectors import req

KEY = "test-key-not-real"


class Fake:
    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers  # function name -> JSON answer
        self.urls: list[str] = []

    def get(
        self,
        url: str,
        *,
        allowed_hosts: frozenset[str],
        redirect_hosts: frozenset[str] = frozenset(),
    ) -> Fetched:
        assert allowed_hosts == frozenset({"www.alphavantage.co"})
        self.urls.append(url)
        for function, answer in self.answers.items():
            if f"function={function}" in url:
                return Fetched(url, 200, json.dumps(answer).encode(), "application/json")
        raise AssertionError(url)


def listing(
    symbol: str, name: str, region: str = "United States", kind: str = "Equity"
) -> dict[str, str]:
    return {"1. symbol": symbol, "2. name": name, "3. type": kind, "4. region": region}


def article(label: str, ticker: str = "NKE") -> dict[str, Any]:
    return {
        "title": "Story",
        "url": "https://news.example/a",
        "ticker_sentiment": [{"ticker": ticker, "ticker_sentiment_label": label}],
    }


NIKE_SEARCH = {  # shaped like the provider's real answer for "nike" on 2026-10-19
    "bestMatches": [
        listing("0QZ6.LON", "NIKE", region="United Kingdom"),
        listing("NKE", "Nike Inc - Class B"),
        listing("NKE.DEX", "Nike Inc", region="XETRA"),
        listing("NKE.TRT", "NIKE CDR (CAD Hedged)", region="Toronto"),
        listing("NIKEF", "Nike Fund", kind="Mutual Fund"),
    ]
}


def connect(answers: dict[str, Any]) -> tuple[AlphaVantageNewsConnector, MemoryStorage, Fake]:
    storage = MemoryStorage()
    fetcher = Fake(answers)
    return AlphaVantageNewsConnector(fetcher, SnapshotStore(storage), KEY), storage, fetcher


def manifest(storage: MemoryStorage, ref: str) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(storage.objects[ref.split("#")[0].removeprefix("snapshot://")])
    return out


def test_adverse_search_finds_the_one_listing_and_keeps_both_answers() -> None:
    feed = {"feed": [article("Bearish"), article("Neutral"), article("Bearish", ticker="ADDYY")]}
    connector, storage, fetcher = connect({"SYMBOL_SEARCH": NIKE_SEARCH, "NEWS_SENTIMENT": feed})
    result = connector.execute(req(name="NIKE, Inc.", jurisdictions=["US"]))
    assert result.items == 3
    assert "tickers=NKE&" in fetcher.urls[1]
    out = manifest(storage, result.provenance_ref)
    assert out["searched"] == {"legal_name": "NIKE, Inc.", "symbol": "NKE"}
    assert out["files"][0]["region"] == "United States"
    assert out["provider_negative_label_count"] == 1  # only labels for the company's own share
    assert "discovery-only" in out["limitations"]
    assert len(storage.objects) == 3  # symbol search, news, manifest


def test_the_key_is_sent_but_never_saved() -> None:
    connector, storage, fetcher = connect(
        {"SYMBOL_SEARCH": NIKE_SEARCH, "NEWS_SENTIMENT": {"feed": []}}
    )
    connector.execute(req(name="Nike Inc", jurisdictions=["US"]))
    assert all(f"apikey={KEY}" in u for u in fetcher.urls)
    assert all(KEY.encode() not in body for body in storage.objects.values())


def test_look_alike_listings_are_never_guessed_between() -> None:
    connector, storage, _ = connect({"SYMBOL_SEARCH": NIKE_SEARCH})
    with pytest.raises(PermanentConnectorError) as e:
        connector.execute(req(name="Nike Inc", jurisdictions=["FR"]))  # two exact, none in FR
    assert e.value.code == "no_unique_match"
    connector, storage, _ = connect({"SYMBOL_SEARCH": {"bestMatches": []}})
    with pytest.raises(PermanentConnectorError) as e2:
        connector.execute(req(name="Acme Trading Ltd"))
    assert e2.value.code == "no_unique_match"
    assert storage.objects == {}


def test_industry_news_uses_the_providers_topic_and_unknown_industries_are_not_guessed() -> None:
    connector, storage, fetcher = connect({"NEWS_SENTIMENT": {"feed": [article("Neutral")]}})
    result = connector.execute(req(category=Category.COUNTRY_INDUSTRY))  # industry "Footwear"
    assert "topics=retail_wholesale" in fetcher.urls[0] and len(fetcher.urls) == 1
    out = manifest(storage, result.provenance_ref)
    assert out["searched"]["topic"] == "retail_wholesale"
    assert "provider_negative_label_count" not in out
    with pytest.raises(PermanentConnectorError) as e:
        connector.execute(req(category=Category.COUNTRY_INDUSTRY, industry="Gemstones"))
    assert e.value.code == "no_topic"
    with pytest.raises(PermanentConnectorError) as e2:
        connector.execute(req(category=Category.COUNTRY_INDUSTRY, industry=None))
    assert e2.value.code == "no_industry"


@pytest.mark.parametrize(
    ("answer", "error", "code"),
    [
        ({"Information": "Our standard API rate limit is 25 requests per day."}, "retry", ""),
        ({"Note": "Thank you! 5 calls per minute."}, "retry", ""),
        ({"Information": "The **demo** API key is for demo purposes only."}, "perm", "key_refused"),
        ({"Information": "This is a premium endpoint."}, "perm", "premium_required"),
        ({"Information": "Something else."}, "perm", "refused"),
        ({"Error Message": "Invalid API call."}, "perm", "bad_request"),
        ({"items": "0"}, "perm", "bad_response"),
    ],
)
def test_provider_refusals_are_classified(answer: dict[str, str], error: str, code: str) -> None:
    connector, storage, _ = connect({"NEWS_SENTIMENT": answer})
    if error == "retry":
        with pytest.raises(RetryableConnectorError):
            connector.execute(req(category=Category.COUNTRY_INDUSTRY))
    else:
        with pytest.raises(PermanentConnectorError) as e:
            connector.execute(req(category=Category.COUNTRY_INDUSTRY))
        assert e.value.code == code
    assert storage.objects == {}


def test_a_name_is_needed_and_a_key_is_required() -> None:
    connector, _, _ = connect({})
    with pytest.raises(PermanentConnectorError) as e:
        connector.execute(req(name=None))
    assert e.value.code == "no_name"
    with pytest.raises(ValueError, match="key"):
        AlphaVantageNewsConnector(Fake({}), SnapshotStore(MemoryStorage()), " ")


def test_share_class_labels_are_ignored_when_matching_names() -> None:
    assert listing_name("Nike Inc - Class B") == "nike"
    assert listing_name("Acme Corp Common Stock") == "acme"
    assert listing_name("NIKE CDR (CAD Hedged)") != "nike"


def test_topic_map() -> None:
    assert topic_for("Enterprise software") == "technology"
    assert topic_for("Commercial banking") == "finance"
    assert topic_for("Gemstones") is None


def test_the_worker_adds_the_connector_only_when_a_key_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import AppEnv, AuthMode, Settings
    from scripts import worker

    class NoStorage:
        def __init__(self, **kwargs: object) -> None:
            pass

        def ensure_bucket(self) -> None:
            pass

    monkeypatch.setattr(worker, "S3Storage", NoStorage)
    monkeypatch.setenv("CONNECTOR_CONTACT", "test@example.org")
    settings = Settings(
        app_env=AppEnv.TEST,
        auth_mode=AuthMode.STUB,
        database_url="postgresql://unused",
        s3_endpoint_url="http://localhost:1",
        s3_bucket="b",
        s3_access_key="a",  # type: ignore[arg-type]
        s3_secret_key="s",  # type: ignore[arg-type]
        clamav_host="localhost",
    )
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)
    assert worker.build_connectors(settings).get("alpha-vantage-news") is None
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", KEY)
    assert worker.build_connectors(settings).get("alpha-vantage-news") is not None
