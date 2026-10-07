# Runbook: try the API on your own computer

For the Product Owner and developers. Nothing here touches the cloud or real data.

## One-time setup
1. Docker Desktop is running (the whale icon says "Engine running").
2. Start the local database: from the project folder run
   `docker compose -f infra/docker-compose.dev.yml up -d`
3. Install Python 3.12 and `uv` (already done on the build machine).

## Start it
```
cd api
uv run python scripts/dev_server.py
```
It prepares the local database, prints a **test token for each role**, and starts the API.

## Try it
1. Open http://127.0.0.1:8000/docs in your browser.
2. Click **Authorize** (top right), paste one token from the terminal, click Authorize, then Close.
3. Open an endpoint, click **Try it out**, then **Execute**.

| Try this | Expected |
|---|---|
| `GET /health` (no token needed) | `{"status":"ok", ...}` |
| `GET /me` with the underwriter token | the underwriter's permissions |
| `GET /audit-events` with the underwriter token | **403 Not permitted** (underwriters cannot read the audit log) |
| `GET /audit-events` with the **auditor** token | the list of events for `demo-tenant`, including the 403 you just caused |
| `GET /audit-events` with the **other-tenant auditor** token | an empty list: they cannot see `demo-tenant`'s events |
| `GET /me` with no token (click Authorize, Logout) | **401 Authentication required** |

Every response has an `X-Request-ID` header; the same ID appears in the audit event.

## Run the UI and the API together
1. Start the API as above (it already allows the UI at port 3000).
2. In a second PowerShell window: `cd web` then `npm run dev`, and open http://localhost:3000.
3. The UI is not connected to the API yet; that is the front end's next step. See
   `docs/api/ui-integration.md` for what it connects to and the rules it follows.

## Stop it
Press `Ctrl+C` in the terminal. Tokens stop working when the server stops.

## Safety
- `dev_server.py` refuses to run unless `APP_ENV=local`, and the stub login is refused by the app
  itself in staging and production.
- Tokens are fake and only valid against your running copy. Do not share the terminal output anyway.
- To wipe your local test data: `docker compose -f infra/docker-compose.dev.yml down -v`.

## Run the automated tests instead
```
cd api
uv run pytest
```
Set `TEST_DATABASE_URL` to run the database tests too (see the database migrations runbook).
