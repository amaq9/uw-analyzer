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
| `GET /api/v1/me` with the underwriter token | the underwriter's permissions |
| `GET /api/v1/audit-events` with the underwriter token | **403 Not permitted** (underwriters cannot read the audit log) |
| `GET /api/v1/audit-events` with the **auditor** token | the list of events for `demo-tenant`, including the 403 you just caused |
| `GET /api/v1/audit-events` with the **other-tenant auditor** token | an empty list: they cannot see `demo-tenant`'s events |
| `GET /api/v1/me` with no token (click Authorize, Logout) | **401 Authentication required** |

Every response has an `X-Request-ID` header; the same ID appears in the audit event.

## Run the UI and the API together
1. Start the API as above (it already allows the UI at port 3000).
2. In a second PowerShell window: `cd web` then `npm run dev`, and open http://localhost:3000.
3. The UI is not connected to the API yet; that is the front end's next step. See
   `docs/api/ui-integration.md` for what it connects to and the rules it follows.

## Document uploads (storage and virus scanner)
Uploads need two more local containers, started with the rest: `docker compose -f infra/docker-compose.dev.yml up -d`
(services `s3` and `clamav`). `scripts/dev_server.py` configures them automatically with throwaway local
credentials and creates the bucket. If they are not running, uploads answer 503 ("not set up" or
"could not be completed") and nothing else is affected. The first start of the scanner can take a minute.

- Try it at http://127.0.0.1:8000/docs: sign in with an underwriter token, create a case, then use
  `POST /api/v1/cases/{id}/documents` (choose a PDF and a category).
- Files you can expect to be refused: programs, files whose name does not match their contents, Word or Excel
  files with macros, PDFs with scripts, oversize files, and anything the scanner flags.
- **Antivirus on your computer:** to test the scanner, the standard harmless **EICAR** test string is used. Windows
  Defender will quarantine any file containing it and may show a "threat found" notice. That is the test working
  and is not a real virus. The automated tests send it from memory, never from a file.

### Running the real-service tests
```
bash infra/ci/start-test-services.sh      # starts the two containers (same as CI)
cd api
# set these four for the session, then run pytest
TEST_S3_ENDPOINT_URL=http://localhost:8333  TEST_S3_ACCESS_KEY=devaccesskey
TEST_S3_SECRET_KEY=devsecretkey123          TEST_CLAMAV_HOST=localhost
```
The script and the compose services use the same ports, so stop one set (`docker rm -f uw-test-s3 uw-test-clamav`)
before starting the other. Without these settings the real-service tests skip locally; in CI they must run.

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
