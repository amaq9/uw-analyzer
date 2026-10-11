"""Research worker (FR-2.5). Takes queued research runs from the database and executes them.

    cd api
    uv run python scripts/worker.py          # keep working until stopped (Ctrl+C)
    uv run python scripts/worker.py --once   # work through what is queued, then exit

No real connectors exist yet, so planned steps are recorded as SKIPPED ("No connector is
implemented"). Add connectors to CONNECTORS below as they are built.
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
from app.research.connectors import ConnectorSet  # noqa: E402
from app.research.executor import Executor  # noqa: E402
from app.research.run_store import PostgresRunQueue  # noqa: E402
from app.research.store import PostgresResearchStore  # noqa: E402
from app.sources.store import PostgresSourceStore  # noqa: E402

CONNECTORS = ConnectorSet()  # no real connectors yet
DEFAULT_DB = "postgresql+psycopg://uwanalyzer:localdevonly@localhost:5432/uwanalyzer"
IDLE_SECONDS = 2.0


def build_executor(settings: Settings, connectors: ConnectorSet = CONNECTORS) -> Executor:
    engine = create_engine(settings.database_url)
    return Executor(
        runs=PostgresResearchStore(engine),
        queue=PostgresRunQueue(engine),
        sources=PostgresSourceStore(engine),
        cases=PostgresCaseStore(engine),
        connectors=connectors,
    )


def main(argv: list[str]) -> int:
    os.environ.setdefault("APP_ENV", "local")
    os.environ.setdefault("AUTH_MODE", "stub")
    os.environ.setdefault("DATABASE_URL", DEFAULT_DB)
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
