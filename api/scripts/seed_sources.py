"""Register the free public registries that have connectors (LOCAL USE ONLY).

    cd api
    uv run python scripts/seed_sources.py            # tenant demo-tenant
    ASSISTED_TENANT=my-tenant uv run python scripts/seed_sources.py

This is the same thing an administrator does through POST /api/v1/sources. It only records what
the product can reach; whether a source was actually used is shown by the connector-call log.
Running it twice is safe: existing entries are left alone.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from scripts.assisted import _client  # noqa: E402

SOURCES = [
    {
        "key": "sec-edgar",
        "name": "SEC EDGAR (U.S. filings and reported financial data)",
        "source_class": "OFFICIAL",
        "source_type": "financial_filings",
        "jurisdictions": ["US"],
        "access_category": "ACTUALLY_ACCESSIBLE",
        "auth_state": "NOT_REQUIRED",
        "terms_notes": "Free public data. Requests must identify a contact; at most 10 per second.",
        "rate_limit_per_minute": 300,
    },
    {
        "key": "gleif",
        "name": "GLEIF Global LEI Register (legal entity identity and ownership)",
        "source_class": "OFFICIAL",
        "source_type": "company_registry",
        "jurisdictions": ["GLOBAL"],
        "access_category": "ACTUALLY_ACCESSIBLE",
        "auth_state": "NOT_REQUIRED",
        "terms_notes": "Free public data (CC0).",
        "rate_limit_per_minute": 60,
    },
]


def main() -> int:
    client, idp = _client()
    tenant = os.environ.get("ASSISTED_TENANT", "demo-tenant")
    token = idp.issue(
        subject="seed-admin", tenant_id=tenant, roles=["administrator"], ttl_seconds=300
    )
    headers = {"Authorization": f"Bearer {token}"}
    return _seed(client, headers)


def _seed(client: TestClient, headers: dict[str, str]) -> int:
    for source in SOURCES:
        r = client.post("/api/v1/sources", json=source, headers=headers)
        label = {201: "registered", 409: "already registered"}.get(
            r.status_code, f"FAILED {r.text}"
        )
        print(f"{source['key']}: {label}")
        if r.status_code not in (201, 409):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
