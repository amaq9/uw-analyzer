# API contract

`openapi.json` in this folder is the single contract between the back end (Claude Code) and the front end (Codex). It is generated from the API code, never hand-edited.

- **Regenerate** (from `api/`): `uv run python scripts/export_openapi.py`
- **Drift check:** a test (`api/tests/test_openapi_contract.py`) fails if this file does not match the code, so the spec and the API cannot disagree.
- **Changes:** a back-end change that alters a request or response shape updates this file in the same PR. Breaking changes need Product Owner approval before merge (AGENTS.md section 3).
- **Auth:** all endpoints except `GET /health` need `Authorization: Bearer <token>`. `401` means unauthenticated; `403` means authenticated but not permitted; a `404` can also mean the object belongs to another tenant.

## Endpoints (v0.1.0)

Every response carries an `X-Request-ID` header (send your own safe ID in the request to trace a call). Quote it when reporting a problem.


| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | none | Liveness: `{status, version}` |
| GET | `/me` | bearer | Caller's `subject`, `tenant_id`, `roles`, `permissions` |
| GET | `/audit-events?limit=50` | bearer, `audit:read` (auditor) | The caller's own tenant's audit events, newest first (limit 1-100). Reading is itself audited |

There are deliberately no endpoints that approve, decline, rate or set a limit (P-09).
