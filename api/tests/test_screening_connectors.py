"""OFAC, World Bank and GDELT connectors with a fake fetcher: no network in tests."""

import json
import uuid
from typing import Any

import pytest

from app.research.connectors import (
    ConnectorRequest,
    PermanentConnectorError,
    RetryableConnectorError,
)
from app.research.fetch import Fetched, HttpsFetcher
from app.research.plan import Category
from app.research.screening_connectors import (
    GdeltNewsConnector,
    OfacSdnConnector,
    WorldBankConnector,
)
from app.research.snapshots import SnapshotStore
from tests.test_public_connectors import MemoryStorage

CASE = uuid.uuid4()


class Fake:
    def __init__(self, routes: dict[str, bytes]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, frozenset[str]]] = []

    def get(
        self,
        url: str,
        *,
        allowed_hosts: frozenset[str],
        redirect_hosts: frozenset[str] = frozenset(),
    ) -> Fetched:
        self.calls.append((url, redirect_hosts))
        for prefix, body in self.routes.items():
            if url.startswith(prefix):
                return Fetched(url, 200, body, "text/csv")
        raise AssertionError(url)


def req(
    name: str | None = "Acme Trading Ltd",
    category: Category = Category.ADVERSE_SEARCH,
    **kw: object,
) -> ConnectorRequest:
    base = {
        "case_id": CASE,
        "tenant_id": "t1",
        "category": category,
        "source_key": "x",
        "jurisdictions": ["CA", "US"],
        "legal_name": name,
        "registration_number": None,
        "industry": "Footwear",
    }
    base.update(kw)
    return ConnectorRequest(**base)  # type: ignore[arg-type]


def sdn_csv(extra: list[str]) -> bytes:
    filler = [
        f'{i},"FILLER ENTITY {i}",-0- ,"CUBA",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- '
        for i in range(200)
    ]
    return "\n".join(filler + extra).encode("latin-1")


def alt_csv(extra: list[str]) -> bytes:
    filler = [f'{i},{i},"aka","FILLER ALIAS {i}",-0- ' for i in range(200)]
    return "\n".join(filler + extra).encode("latin-1")


def ofac(sdn: list[str], alt: list[str]) -> tuple[OfacSdnConnector, MemoryStorage, Fake]:
    storage = MemoryStorage()
    fetcher = Fake(
        {
            "https://sanctionslistservice.ofac.treas.gov/api/publicationpreview/exports/sdn.csv": sdn_csv(
                sdn
            ),
            "https://sanctionslistservice.ofac.treas.gov/api/publicationpreview/exports/alt.csv": alt_csv(
                alt
            ),
        }
    )
    return OfacSdnConnector(fetcher, SnapshotStore(storage)), storage, fetcher


def result_of(
    connector: OfacSdnConnector, storage: MemoryStorage, request: ConnectorRequest
) -> dict[str, Any]:
    ref = connector.execute(request).provenance_ref
    key = ref.split("#")[0].removeprefix("snapshot://")
    out: dict[str, Any] = json.loads(storage.objects[key])
    return out


def test_ofac_exact_match_on_name_ignoring_suffixes_and_case() -> None:
    sdn = ['900,"ACME TRADING CO.",-0- ,"RUSSIA-EO14024",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ']
    connector, storage, fetcher = ofac(sdn, [])
    out = result_of(connector, storage, req())
    assert out["exact_match_count"] == 1
    assert out["exact_matches"][0]["entity_number"] == "900"
    assert out["exact_matches"][0]["program"] == "RUSSIA-EO14024"
    assert "not a compliance screening" in out["limitations"]
    assert all(rh for _, rh in fetcher.calls)  # the signed file host was named for the redirect
    assert len(storage.objects) == 3  # both raw lists and the result are kept


def test_ofac_alias_match_and_possible_matches_are_separated() -> None:
    sdn = [
        '901,"GLOBAL SHIPPING GROUP",-0- ,"SDGT",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ',
        '902,"ACME TRADING HOLDINGS INTERNATIONAL",-0- ,"SDGT",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ',
    ]
    alt = ['901,5,"aka","ACME TRADING LIMITED",-0- ']
    connector, storage, _ = ofac(sdn, alt)
    out = result_of(connector, storage, req())
    assert [m["entity_number"] for m in out["exact_matches"]] == ["901"]
    assert out["exact_matches"][0]["matched_on"] == "alias"
    assert [m["entity_number"] for m in out["possible_matches"]] == ["902"]


def test_ofac_single_word_names_only_match_exactly_and_no_hit_is_a_real_result() -> None:
    sdn = ['903,"NIKE SPORTS TRADING",-0- ,"SDGT",-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ,-0- ']
    connector, storage, _ = ofac(sdn, [])
    out = result_of(connector, storage, req(name="Nike, Inc."))
    assert (out["exact_match_count"], out["possible_match_count"]) == (0, 0)
    assert out["normalised_words"] == ["nike"] and out["files"][0]["sha256"]


def test_ofac_refuses_missing_names_and_truncated_lists() -> None:
    connector, storage, _ = ofac([], [])
    with pytest.raises(PermanentConnectorError) as e:
        connector.execute(req(name=None))
    assert e.value.code == "no_name"
    short = OfacSdnConnector(Fake({"https://": b"1,x\n2,y\n"}), SnapshotStore(MemoryStorage()))
    with pytest.raises(PermanentConnectorError) as e2:
        short.execute(req())
    assert e2.value.code == "bad_response"


def test_world_bank_bundles_each_country_and_indicator() -> None:
    body = json.dumps([{"page": 1}, [{"date": "2025", "value": 2.1}]]).encode()
    storage = MemoryStorage()
    fetcher = Fake({"https://api.worldbank.org/v2/country/": body})
    connector = WorldBankConnector(fetcher, SnapshotStore(storage))
    result = connector.execute(req(jurisdictions=["CA", "US", "GLOBAL"]))
    assert result.items == 6  # two countries, three indicators; GLOBAL is skipped
    bundle = json.loads(next(iter(storage.objects.values())))
    assert {r["country"] for r in bundle["responses"]} == {"CA", "US"}
    assert "not a sector outlook" in bundle["limitations"]


def test_world_bank_refuses_no_country_and_unexpected_data() -> None:
    connector = WorldBankConnector(
        Fake({"https://": b'{"message": "error"}'}), SnapshotStore(MemoryStorage())
    )
    with pytest.raises(PermanentConnectorError) as e:
        connector.execute(req(jurisdictions=["GLOBAL"]))
    assert e.value.code == "no_country"
    with pytest.raises(PermanentConnectorError) as e2:
        connector.execute(req(jurisdictions=["US"]))
    assert e2.value.code == "bad_response"


def gdelt(body: bytes) -> tuple[GdeltNewsConnector, MemoryStorage, Fake, list[float]]:
    storage = MemoryStorage()
    pauses: list[float] = []
    fetcher = Fake({"https://api.gdeltproject.org/api/v2/doc/doc": body})
    return (
        GdeltNewsConnector(fetcher, SnapshotStore(storage), pauses.append),
        storage,
        fetcher,
        pauses,
    )


def test_gdelt_adverse_query_uses_the_name_without_suffixes_and_waits_first() -> None:
    body = json.dumps(
        {"articles": [{"title": "Lawsuit filed", "url": "https://n.example/a"}]}
    ).encode()
    connector, storage, fetcher, pauses = gdelt(body)
    result = connector.execute(req(name="NIKE, Inc."))
    assert pauses == [6.0] and result.items == 1
    assert "%22NIKE%22" in fetcher.calls[0][0] and "lawsuit" in fetcher.calls[0][0]
    record = json.loads(next(iter(storage.objects.values())))
    assert record["article_count"] == 1 and "discovery-only" in record["limitations"]


def test_gdelt_sector_query_needs_an_industry_and_empty_answers_are_logged() -> None:
    connector, storage, fetcher, _ = gdelt(b"")
    result = connector.execute(req(category=Category.COUNTRY_INDUSTRY))
    assert result.items == 0 and "Footwear" in fetcher.calls[0][0]
    assert json.loads(next(iter(storage.objects.values())))["response"] is None
    with pytest.raises(PermanentConnectorError) as e:
        connector.execute(req(category=Category.COUNTRY_INDUSTRY, industry=None))
    assert e.value.code == "no_industry"


def test_gdelt_refuses_unreadable_responses() -> None:
    connector, storage, _, _ = gdelt(b"<html>nope</html>")
    with pytest.raises(PermanentConnectorError):
        connector.execute(req())
    assert storage.objects == {}


def test_gdelt_titles_with_control_characters_or_stray_backslashes_are_read() -> None:
    body = b'{"articles": [{"title": "Nike\tcase\x01 C:\\dir \\x", "url": "https://n.example/a"}]}'
    connector, storage, _, _ = gdelt(body)
    assert connector.execute(req()).items == 1
    record = json.loads(next(iter(storage.objects.values())))
    assert record["response"]["articles"][0]["title"] == "Nike\tcase\x01 C:\\dir \\x"


def test_gdelt_rate_limit_note_is_retryable_not_a_bad_response() -> None:
    note = b"Please limit requests to one every 5 seconds or contact us for larger queries."
    connector, storage, _, _ = gdelt(note)
    with pytest.raises(RetryableConnectorError):
        connector.execute(req())
    assert storage.objects == {}


def test_fetcher_follows_at_most_one_redirect_and_only_to_named_hosts() -> None:
    fetcher = HttpsFetcher("test@example.org")
    with pytest.raises(PermanentConnectorError) as e:
        fetcher._get(  # noqa: SLF001
            "https://evil.example/x", frozenset({"a.example"}), frozenset(), may_redirect=True
        )
    assert e.value.code == "host_not_allowed"
