# ADR 0011: Research executor, Postgres queue and connector-call log (Phase 2, slice 3)

- **Status:** Accepted, 2026-10-11 (Product Owner delegated Phase 2 to Claude Code; ADR 0003 local pilot)
- **Date:** 2026-10-11 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Decision
1. **Postgres is the queue**, not Redis. `POST .../research-runs/{id}/start` sets the run to `QUEUED`; a
   worker (`api/scripts/worker.py`) claims the oldest queued run with `SELECT ... FOR UPDATE SKIP LOCKED`,
   so two workers never take the same run and a crash leaves the state in the database. One less moving
   part for a local pilot; Redis stays available if throughput ever needs it.
2. **Per-step state, timeout, bounded retries (FR-2.5).** Each connector call runs under a timeout;
   retryable errors and timeouts back off exponentially (1 s doubling, capped) up to `max_attempts`
   (default 3); permanent errors fail the step at once. A crashed connector fails its step, never the worker.
3. **Resumable and idempotent.** Finished steps (`SUCCEEDED`, `FAILED`, `SKIPPED`, `NOT_AVAILABLE`) are
   never run again. A re-claimed run resets steps left `RUNNING` by a dead worker. A `FAILED` run can be
   started again: failed steps get three more attempts, and attempt numbers continue.
4. **Connector-call log (FR-2.6), append-only** (`connector_calls`, migration 0010): case, run, step, source,
   attempt, what the call does, the source's access category at that moment, start and end, outcome, error
   class and the provenance reference returned. Database triggers refuse UPDATE, DELETE, TRUNCATE.
5. **Access can only come from an executed call (FR-2.7, P-01).** There is no API to write the log. A call
   counts as `SUCCESS` only with a non-empty provenance reference (executor check and database CHECK). A step
   reads `accessed: true` only if such a call exists. `accessed` is not verification (P-04); verification
   arrives in Phase 3.
6. **Nothing is simulated.** The product ships no connectors. A planned step whose source has no connector
   is `SKIPPED` with "No connector is implemented for this source, so it was not searched." Tests use
   test-only doubles.
7. **P-03 re-checked at start.** The entity gate is enforced when queuing, not only when planning.
8. **P-10:** connector versions used are written into the run's `versions.connectors` as they are used.

## Limits and next
- A timed-out connector thread cannot be killed; it is abandoned and its result ignored.
- Real connectors, evidence and claims (Phase 3) and the LLM adapter (ADR 0006) come next. Needs the
  Product Owner: the first public data source(s) and an Anthropic API key.
