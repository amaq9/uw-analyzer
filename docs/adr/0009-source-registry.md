# ADR 0009: Source and connector registry (Phase 2, slice 1)

- **Status:** Proposed, 2026-10-11 (ADR 0003 local pilot; Phase 2 started at the Product Owner's request)
- **Date:** 2026-10-11 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Context
FR-2.1/2.2: the application must know what each source can and cannot give before relying on it, and
must never claim access it did not have (P-01, FR-2.7). Licensed connectors are never assumed available
or simulated.

## Decision
1. **A per-tenant registry** (`sources`, migration 0007) holding class, type, jurisdictions, access
   category, auth state, terms notes, rate limit and health. **No seeded entries:** nothing is listed
   until the administrator registers it.
2. **Capability is not access.** The registry never records that a source was used. That is the job of
   the connector-call log (next slice), written only by executed calls.
3. **No credentials** are accepted, stored or returned (unknown fields are rejected). Secrets stay in a
   secrets store, referenced by name later.
4. **Honest states.** `ACTUALLY_ACCESSIBLE` cannot be combined with a missing credential (validated and
   database-checked).
5. **Permissions, no change to the ADR 0001 role table:** write = `admin:manage`; read = `admin:manage`,
   `case:read` or `research:run`. Cross-tenant access returns 404 and is audited.
6. **Health is set by the administrator for now**; automatic health checks come with connectors.
7. Optimistic concurrency (`expected_version`), audit events for create and update (field names and
   access category only).

## Consequences / next
Next slices: research plan from the case and registry (FR-2.3), connector-call log (FR-2.6), job queue
and worker (FR-2.5), LLM interface (ADR 0006). Needs the Product Owner at that point: an Anthropic API
key and the first public data source(s).

## Addendum, 2026-10-20: health observed from connector calls
Item 6 said automatic health checks would come with connectors; they now exist. After each research step the
executor records the source's health from the logged calls: a success sets **HEALTHY**; a step that fails after
its retries on a temporary error (network, rate limit, timeout) sets **DEGRADED**. A permanent error (no unique
match, no name, a refused request) is about the request, so it changes nothing. The system never sets **DOWN**
and never overwrites an administrator's DOWN, because DOWN takes a source out of research plans and stays a
person's decision. Observed health is not a configuration change: it updates `health_checked_at` but not the
source's `version`, so an administrator's edit in progress is not refused as stale. The call log remains the
record of what happened; the health field is a summary of the latest outcome.
