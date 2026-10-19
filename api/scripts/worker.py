"""Research worker (FR-2.5). Takes queued research runs from the database and executes them.

    cd api
    uv run python scripts/worker.py          # keep working until stopped (Ctrl+C)
    uv run python scripts/worker.py --once   # work through what is queued, then exit

Connectors for the free public sources (SEC EDGAR, GLEIF, OFAC, World Bank, GDELT news) are
enabled when CONNECTOR_CONTACT (your contact address, sent to the registries as required) and
the document storage settings are set. Otherwise planned steps are recorded as SKIPPED
("No connector is implemented"). Alpha Vantage market news is added only when
ALPHA_VANTAGE_API_KEY is also set (ADR 0023).
"""

import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine  # noqa: E402

from app.cases.store import PostgresCaseStore  # noqa: E402
from app.config import Settings  # noqa: E402
from app.documents.storage import S3Storage  # noqa: E402
from app.research.alpha_vantage import AlphaVantageNewsConnector  # noqa: E402
from app.research.connectors import Connector, ConnectorSet  # noqa: E402
from app.research.executor import Executor  # noqa: E402
from app.research.fetch import HttpsFetcher  # noqa: E402
from app.research.public_connectors import GleifConnector, SecEdgarConnector  # noqa: E402
from app.research.run_store import PostgresRunQueue  # noqa: E402
from app.research.screening_connectors import (  # noqa: E402
    GdeltNewsConnector,
    OfacSdnConnector,
    WorldBankConnector,
)
from app.research.snapshots import SnapshotStore  # noqa: E402
from app.research.store import PostgresResearchStore  # noqa: E402
from app.sources.store import PostgresSourceStore  # noqa: E402

DEFAULT_DB = "postgresql+psycopg://uwanalyzer:localdevonly@localhost:5432/uwanalyzer"
LOCAL_STORAGE = {  # local Docker storage (same throwaway values as dev_server.py)
    "S3_ENDPOINT_URL": "http://localhost:8333",
    "S3_BUCKET": "uw-documents",
    "S3_ACCESS_KEY": "devaccesskey",
    "S3_SECRET_KEY": "devsecretkey123",
    "CLAMAV_HOST": "localhost",
}
IDLE_SECONDS = 2.0


def build_connectors(settings: Settings) -> ConnectorSet:
    """The free public registries, if storage and a contact address are configured.

    Set CONNECTOR_CONTACT to an address the registries can reach you at (SEC EDGAR requires one).
    Without it, or without document storage, no connector is created and steps are SKIPPED."""
    contact = os.environ.get("CONNECTOR_CONTACT", "").strip()
    if not (contact and settings.documents_configured):
        logging.getLogger("uw.worker").warning(
            "No connectors enabled: set CONNECTOR_CONTACT and the document storage settings."
        )
        return ConnectorSet()
    assert settings.s3_access_key and settings.s3_secret_key  # noqa: S101
    assert settings.s3_endpoint_url and settings.s3_bucket  # noqa: S101
    storage = S3Storage(
        endpoint_url=settings.s3_endpoint_url,
        bucket=settings.s3_bucket,
        access_key=settings.s3_access_key.get_secret_value(),
        secret_key=settings.s3_secret_key.get_secret_value(),
        region=settings.s3_region,
    )
    storage.ensure_bucket()
    fetcher = HttpsFetcher(contact)
    snapshots = SnapshotStore(storage)
    sec = SecEdgarConnector(fetcher, snapshots)
    gleif = GleifConnector(fetcher, snapshots)
    others: list[Connector] = [
        OfacSdnConnector(fetcher, snapshots),
        WorldBankConnector(fetcher, snapshots),
        GdeltNewsConnector(fetcher, snapshots),
    ]
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    if api_key:
        others.append(AlphaVantageNewsConnector(fetcher, snapshots, api_key))
    everything: list[Connector] = [sec, gleif, *others]
    return ConnectorSet({c.key: c for c in everything})


def build_executor(settings: Settings, connectors: ConnectorSet | None = None) -> Executor:
    engine = create_engine(settings.database_url)
    return Executor(
        runs=PostgresResearchStore(engine),
        queue=PostgresRunQueue(engine),
        sources=PostgresSourceStore(engine),
        cases=PostgresCaseStore(engine),
        connectors=connectors if connectors is not None else build_connectors(settings),
    )


def main(argv: list[str]) -> int:
    os.environ.setdefault("APP_ENV", "local")
    os.environ.setdefault("AUTH_MODE", "stub")
    os.environ.setdefault("DATABASE_URL", DEFAULT_DB)
    for name, value in LOCAL_STORAGE.items():
        os.environ.setdefault(name, value)
    logging.basicConfig(level=logging.INFO)
    executor = build_executor(Settings())  # type: ignore[call-arg]
    once = "--once" in argv
    while True:
        worked = executor.work_once()
        if once and not worked:
            return 0
        if not worked:
            time.sleep(IDLE_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
