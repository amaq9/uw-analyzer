# ADR 0002: Append-only audit events and request correlation IDs

- **Status:** Proposed (implemented in the FR-0.5 PR)
- **Date:** 2026-10-07 (America/Toronto)
- **Decider:** Product Owner (approves). Author: Claude Code.

## Context
FR-0.5 requires an append-only audit event service and correlation/request IDs. The protocol and
SEC-10 require audit events to be separate from diagnostic logs, and AC-10 requires cross-tenant
denials to be logged. Completed work must be explainable later ("who did what, when, and why was
it refused"), which also supports P-08 and P-10.

## Decision
1. **A dedicated `audit_events` table in PostgreSQL**, separate from application logs. Each event has
   an exact order number (`seq`, assigned by the database), a time, tenant, actor, action, outcome,
   resource, correlation ID and a small details map.
2. **Append-only at the database level.** Database triggers make UPDATE, DELETE and TRUNCATE fail with
   "audit_events is append-only". The application cannot edit history even if its own code has a bug.
3. **Correlation IDs.** Every request gets an ID, returned in the `X-Request-ID` response header and
   stored on every audit event it causes. A caller-supplied ID is kept only if it is a safe token
   (8-64 letters, digits, `.`, `_`, `-`); anything else is replaced, which blocks log injection.
4. **What is audited now:** rejected logins, permission denials, cross-tenant denials, and reads of the
   audit log itself. Successful ordinary requests are not audited (noise). Business events (cases,
   evidence, reports) are added by the phase that introduces them, using the same `record_event` helper.
5. **Tenant-scoped reads.** `GET /audit-events` needs the `audit:read` permission and returns only the
   caller's own tenant's events. A cross-tenant denial is filed under the caller's tenant and never
   names the other tenant. Events with no tenant (for example a request with no valid token) are stored
   but are not readable through the API.
6. **Failure behaviour.** If writing an audit event fails, the failure is logged and the original
   decision stands: a denial is still a denial (fail closed). Later business operations that change
   material state must instead fail if their audit event cannot be written; this ADR covers denials only.

## Alternatives considered
- **Log files only:** easy to alter, hard to query per tenant, and mixes diagnostics with evidence.
- **A hash chain across events:** stronger tamper evidence; deferred, see consequences.
- **A separate audit database or service:** more moving parts than needed this early.

## Consequences
- **Not yet true tamper-proof.** A database administrator can still drop the triggers. Before
  production, the application must connect with a restricted database role that has INSERT and SELECT
  on `audit_events` only, and database admin access must be audited (tracked for the infra work, FR-0.3
  and the security checklist). A hash chain or external write-once copy is a candidate hardening step.
- Retention periods are an open decision (PRD section 19); nothing is purged.
- `DATABASE_URL` is required configuration with no default.
- Integration tests need a Postgres: set `TEST_DATABASE_URL` locally (they skip if it is unset) and CI
  provides one (they fail if it is missing there).

## Rollback
Revert the PR and run `alembic downgrade base`. No other table depends on `audit_events` yet.
