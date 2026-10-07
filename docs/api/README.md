# API contract

`openapi.json` in this folder is the single contract between the back end (Claude Code) and the front end (Codex). It is generated from the API code, never hand-edited.

- **Regenerate** (from `api/`): `uv run python scripts/export_openapi.py`
- **Drift check:** a test (`api/tests/test_openapi_contract.py`) fails if this file does not match the code, so the spec and the API cannot disagree.
- **Changes:** a back-end change that alters a request or response shape updates this file in the same PR. Breaking changes need Product Owner approval before merge (AGENTS.md section 3).
- **Auth:** all endpoints except `GET /health` need `Authorization: Bearer <token>`. `401` means unauthenticated; `403` means authenticated but not permitted; a `404` can also mean the object belongs to another tenant.

## Conventions
- **Versioned paths:** everything except `GET /health` lives under `/api/v1/`.
- **Standard error object** on every non-2xx response:
  `{"error": {"code", "message", "correlation_id", "retryable", "field_errors"?}}`. `code` is one of
  `unauthenticated`, `forbidden`, `not_found`, `method_not_allowed`, `conflict`, `validation_error`,
  `rate_limited`, `payload_too_large`, `unsupported_media_type`, `bad_request`, `internal_error`.
  `message` is safe to show to a user. `field_errors` (validation only) lists `{field, message}` and
  never echoes what was submitted. `correlation_id` equals the `X-Request-ID` response header.

## Endpoints (v0.1.0)

Every response carries an `X-Request-ID` header (send your own safe ID in the request to trace a call). Quote it when reporting a problem.


| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Liveness: `{status, version}` |
| GET | `/api/v1/me` | bearer | Caller's `subject`, `tenant_id`, `roles`, `permissions` |
| GET | `/api/v1/audit-events?limit=50` | bearer, `audit:read` (auditor) | The caller's own tenant's audit events, newest first (limit 1-100). Reading is itself audited |
| POST | `/api/v1/cases` | bearer, `case:write` (underwriter, reviewer) | Create a case. Only `legal_name` or `trading_name` is required. Returns 201 with the case and its `information_gaps` |
| GET | `/api/v1/cases?limit=50&offset=0` | bearer, `case:read` | The caller's own tenant's cases, newest first |
| GET | `/api/v1/cases/{id}` | bearer, `case:read` | One case. Another tenant's case returns 404. Viewing is audited |
| PATCH | `/api/v1/cases/{id}` | bearer, `case:write` | Change fields. Send `expected_version`; a stale version returns 409 and saves nothing. Send `null` to clear an optional field |

**Case notes.** `status` is server-controlled (`DRAFT`, `ENTITY_AMBIGUOUS`, `ENTITY_RESOLVED`); sending
`status`, `id`, `owner`, `tenant_id` or `version` is rejected (422). `exposure_amount` is an exact
decimal (send and treat it as a string such as `"1250000.50"`) and must come with `exposure_currency`
(3 letters, such as `CAD`). `information_gaps` lists missing inputs; the system never fills them in.

There are deliberately no endpoints that approve, decline, rate or set a limit (P-09).
