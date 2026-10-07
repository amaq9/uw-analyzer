# Connecting the UI to the API

For Codex (front end) and anyone wiring the UI to the back end. The contract itself is
`openapi.json` in this folder; this page covers everything around it.

## Local development
1. Start the database: `docker compose -f infra/docker-compose.dev.yml up -d`
2. Start the API (from `api/`): `uv run python scripts/dev_server.py`
   - Listens on `http://127.0.0.1:8000` (override with `API_PORT`).
   - Prints a **test token for each role** (valid 8 hours). Tenants: `demo-tenant`, `other-tenant`.
   - Allows browser calls from `http://localhost:3000` and `http://127.0.0.1:3000` only.
3. Start the UI (from `web/`): `npm run dev` (port 3000).

## Rules the UI must follow
- **Base URL** comes from configuration, never hard-coded (for example `NEXT_PUBLIC_API_BASE_URL`;
  local value `http://127.0.0.1:8000`).
- **Types and mocks are generated from `openapi.json`.** Do not hand-write API types (AGENTS.md
  section 3).
- **Auth** is `Authorization: Bearer <token>` on every call except `GET /health`. There are no cookies,
  so there is no CSRF surface and the API never sends or accepts credentials cookies.
- **Status codes to handle:** `401` = not signed in or token invalid/expired (send the user to
  sign-in); `403` = signed in but not permitted (show a clear "you don't have access" message, not a
  crash); `404` can also mean "belongs to another tenant" (show a normal not-found); `422` = the
  request was malformed.
- **Errors have one shape:** `{error: {code, message, correlation_id, retryable, field_errors?}}`
  (see README). Show `message`; use `code` for logic; highlight `field_errors` next to the fields.
- **Show the request ID on errors.** Every response has an `X-Request-ID` header (readable from
  browser code); error bodies repeat it as `correlation_id`. Display it in the error details so users can quote it to support.
- **Never show raw error bodies, tokens or stack traces** to users. Never store tokens in
  `localStorage`; keep them in memory (a real session design comes with the identity provider).
- **P-09 (ADR 0004, amended by ADR 0005):** no approve, decline, rating, score, traffic light or
  credit-limit wording or UI anywhere **today**. ADR 0005 will later allow exactly two labelled places
  (a "Draft recommendation for the underwriter" and the human "Underwriter decision"), only when the
  back end ships them and Product Owner approval is recorded; do not build them early. Never present research readiness as a score or a decision: show plain wording and the
  reason from `blockers[].message`, with no percentage, grade, badge that reads as pass or fail, or
  green/amber/red colouring.
- **Permissions drive the UI.** `GET /api/v1/me` returns the caller's `permissions`; hide or disable
  actions the caller lacks. The server enforces them regardless, so this is for clarity, not security.

## Sign-in during development
Real single sign-on is blocked on the identity-provider decision, so the UI cannot sign users in
yet. Suggested interim: a **development-only** "paste a test token" box, shown only when running
locally (not in a production build), which keeps the token in memory and calls `GET /api/v1/me`. This is
the front end's decision; the back end needs nothing further for it.

## What exists today
| Endpoint | Use it for |
|---|---|
| `GET /health` | API reachable check (no auth) |
| `GET /api/v1/me` | Signed-in state: who, tenant, roles, permissions |
| `GET /api/v1/audit-events` | An auditor-only activity view (`audit:read`) |
| `POST/GET/PATCH /api/v1/cases` | Case intake: create, list, view and edit (see README for rules) |

**Entity resolution screens (AC-01, P-03, P-07).** Show candidates side by side. When
`status` is `ENTITY_AMBIGUOUS`, show a prominent block that explains what is needed (use the
`blockers[].message` from `research-readiness`) and offer an explicit "Choose this entity" action
per candidate, with an optional note. Never auto-select, pre-select or hide this. Once resolved,
show who chose and when, and a "Reopen" action that requires a reason. Disable the choose, add and
reopen actions without `case:write`. Never present readiness as a score or a decision.

**Document upload screen (FR-1.2).** Send `multipart/form-data` with `file` and `category`; always send the
real file (the server judges it by its contents). Check the size limit (20 MB by default) before sending, to
save the user a wait. Handle each result with the server's own `message`: 413, 415 and 422 mean the file was
refused (say so and let them choose another); **503 means nothing was saved and retrying is safe**; 409 means the
case is full. Show the file name as plain text only (never as HTML) and show size, category, who and when.
Download with `fetch` and the `Authorization` header, then save the returned blob: a plain link or an address
containing the token will not work and must not be used. Never show a "verified" or "safe" badge: the scan is a
gate, not a claim about the document's content (P-04).

**Draft recommendation screen (ADR 0005, ADR 0008).** Show the draft clearly labelled with the `notice` and
a visible "Test product" tag, the outcome and amounts, the AI's proposed figure, the summary, each reason
with its evidence (document name and quote, or the web source, its date and quote), the factors that lowered
the amount, the information gaps and the `limitations`. For a reduced amount show requested and
recommended side by side. Older versions stay available. **Never** show a score, grade, percentage,
traffic-light colour, badge that reads as pass or fail, or wording that implies the system decided.
The underwriter's own decision (adopt, change or reject) and the agreement view come next; do not build
them until the contract ships them. `ENTITY_UNCONFIRMED` is a case status: show it as "The legal entity
could not be confirmed or found" with a reopen action that needs a reason.

**Case screens.** Show `information_gaps` clearly (they are a feature, not an error). On `409`
reload the case and let the user redo the edit. Send `expected_version` on every edit. Treat
`exposure_amount` as a string to avoid rounding. Do not offer `status` as an editable field.

Case, entity, evidence and report endpoints arrive with Phases 1 to 5. If the UI needs an endpoint
or field that is missing, request it in the front-end handoff; the Product Owner routes it to the
back end. Neither side changes the other's code.

## Configuration (back end)
`CORS_ALLOWED_ORIGINS` is a JSON list of exact origins, for example
`["https://app.example.com"]`. Wildcards, paths and trailing slashes are rejected at startup, and
staging and production accept `https` only. Empty (the default) allows no browser origins.
