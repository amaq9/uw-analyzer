"""Run the API on your own computer with ready-made test tokens (LOCAL USE ONLY).

    cd api
    uv run python scripts/dev_server.py

Then open http://127.0.0.1:8000/docs, click "Authorize", paste one token, and try the endpoints.
Tokens come from the in-process stub identity provider, which Settings refuses to start outside
APP_ENV=local or test. Nothing here can run in staging or production.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

from app.auth.tokens import StubIdentityProvider  # noqa: E402
from app.config import AppEnv, Settings  # noqa: E402
from app.main import create_app  # noqa: E402

DEFAULT_DB = (
    "postgresql+psycopg://uwanalyzer:localdevonly@localhost:5432/uwanalyzer"  # local Docker
)
TENANT = "demo-tenant"
OTHER_TENANT = "other-tenant"
EIGHT_HOURS = 8 * 60 * 60
PEOPLE = [
    ("underwriter", TENANT),
    ("reviewer", TENANT),
    ("research_analyst", TENANT),
    ("administrator", TENANT),
    ("auditor", TENANT),
    ("auditor", OTHER_TENANT),
]


def main() -> None:
    os.environ.setdefault("APP_ENV", "local")
    os.environ.setdefault("AUTH_MODE", "stub")
    os.environ.setdefault("DATABASE_URL", DEFAULT_DB)
    # Let the local UI (npm run dev, port 3000) call this API from the browser.
    os.environ.setdefault(
        "CORS_ALLOWED_ORIGINS", '["http://localhost:3000","http://127.0.0.1:3000"]'
    )
    # Local document storage and virus scanner (docker compose services s3 and clamav), with
    # throwaway local-only credentials. If they are not running, uploads answer 503 and nothing
    # else is affected.
    os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:8333")
    os.environ.setdefault("S3_BUCKET", "uw-documents")
    os.environ.setdefault("S3_ACCESS_KEY", "devaccesskey")
    os.environ.setdefault("S3_SECRET_KEY", "devsecretkey123")
    os.environ.setdefault("CLAMAV_HOST", "localhost")
    settings = Settings()  # type: ignore[call-arg]
    if settings.app_env is not AppEnv.LOCAL:
        sys.exit("dev_server.py only runs with APP_ENV=local")

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(cfg, "head")  # creates or updates the local audit table

    app = create_app(settings)
    service = app.state.document_service
    if service is not None:
        try:
            service.storage.ensure_bucket()
            print("Document storage is ready (uploads enabled).")
        except Exception:  # local convenience only; uploads simply stay unavailable
            print("Document storage is not running: uploads will answer 503 until it is.")
    idp: StubIdentityProvider = app.state.stub_idp
    print("\nTEST TOKENS (valid 8 hours; they stop working when you stop this server)\n")
    for role, tenant in PEOPLE:
        token = idp.issue(
            subject=f"{role}-demo", tenant_id=tenant, roles=[role], ttl_seconds=EIGHT_HOURS
        )
        print(f"--- {role} in {tenant} ---\n{token}\n")
    print("Open http://127.0.0.1:8000/docs  ->  Authorize  ->  paste a token. Ctrl+C to stop.\n")
    uvicorn.run(
        app, host="127.0.0.1", port=int(os.environ.get("API_PORT", "8000")), log_level="warning"
    )


if __name__ == "__main__":
    main()
