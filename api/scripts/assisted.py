"""Local helper for assisted mode (ADR 0008; LOCAL USE ONLY).

Lets a Claude Code session read a case and its documents, and submit a draft recommendation,
through the same validated API code the UI uses. It runs the app in this process against the local
database, so no token needs to be pasted. It signs in with throwaway stub tokens that only exist
when APP_ENV=local, using the least privilege each step needs:

    reads   -> research_analyst (case:read)
    submit  -> service (draft:import)

It can never record the underwriter's decision: that stays with a named person.

    cd api
    uv run python scripts/assisted.py cases
    uv run python scripts/assisted.py case <case_id>
    uv run python scripts/assisted.py fetch <case_id> <document_id> <output_file>
    uv run python scripts/assisted.py submit <case_id> <draft.json>

Set ASSISTED_TENANT to use a tenant other than demo-tenant.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.auth.tokens import StubIdentityProvider  # noqa: E402
from app.config import AppEnv, Settings  # noqa: E402
from app.main import create_app  # noqa: E402

SUBJECT = "claude-code-session"
DEFAULTS = {
    "APP_ENV": "local",
    "AUTH_MODE": "stub",
    "DATABASE_URL": "postgresql+psycopg://uwanalyzer:localdevonly@localhost:5432/uwanalyzer",
    "S3_ENDPOINT_URL": "http://localhost:8333",
    "S3_BUCKET": "uw-documents",
    "S3_ACCESS_KEY": "devaccesskey",
    "S3_SECRET_KEY": "devsecretkey123",
    "CLAMAV_HOST": "localhost",
}


def _client() -> tuple[TestClient, StubIdentityProvider]:
    for key, value in DEFAULTS.items():
        os.environ.setdefault(key, value)
    settings = Settings()  # type: ignore[call-arg]
    if settings.app_env is not AppEnv.LOCAL:
        sys.exit("assisted.py only runs with APP_ENV=local")
    app = create_app(settings)
    return TestClient(app), app.state.stub_idp


def _headers(idp: StubIdentityProvider, role: str) -> dict[str, str]:
    tenant = os.environ.get("ASSISTED_TENANT", "demo-tenant")
    token = idp.issue(subject=SUBJECT, tenant_id=tenant, roles=[role], ttl_seconds=600)
    return {"Authorization": f"Bearer {token}"}


def _show(label: str, status: int, body: Any) -> None:
    print(f"## {label} (HTTP {status})")
    print(json.dumps(body, indent=2, default=str))


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    client, idp = _client()
    read = _headers(idp, "research_analyst")
    command, args = argv[0], argv[1:]

    if command == "cases" and not args:
        r = client.get("/api/v1/cases?limit=50", headers=read)
        _show("cases", r.status_code, r.json())
    elif command == "case" and len(args) == 1:
        cid = args[0]
        for label, path in (
            ("case", f"/api/v1/cases/{cid}"),
            ("entity candidates", f"/api/v1/cases/{cid}/entity-candidates"),
            ("documents", f"/api/v1/cases/{cid}/documents"),
            ("existing drafts", f"/api/v1/cases/{cid}/draft-recommendations"),
        ):
            r = client.get(path, headers=read)
            _show(label, r.status_code, r.json())
    elif command == "fetch" and len(args) == 3:
        cid, did, out = args
        r = client.get(f"/api/v1/cases/{cid}/documents/{did}/content", headers=read)
        if r.status_code != 200:
            _show("fetch", r.status_code, r.json())
            return 1
        Path(out).write_bytes(r.content)
        print(f"Saved {len(r.content)} bytes to {out}")
    elif command == "submit" and len(args) == 2:
        cid, path = args
        body = json.loads(Path(path).read_text(encoding="utf-8"))
        r = client.post(
            f"/api/v1/cases/{cid}/draft-recommendations",
            json=body,
            headers=_headers(idp, "service"),
        )
        _show("submit draft", r.status_code, r.json())
        return 0 if r.status_code == 201 else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
