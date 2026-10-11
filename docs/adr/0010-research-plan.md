# ADR 0010: Research plan and run records (Phase 2, slice 2)

- **Status:** Accepted, 2026-10-11 (Product Owner delegated Phase 2 to Claude Code; ADR 0003 local pilot)
- **Date:** 2026-10-11 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Decision
1. **Planning is separate from searching.** `POST /api/v1/cases/{id}/research-runs` builds a plan from
   the case and the registry and stores it as a run (`PLANNED`) with steps. Nothing is searched, so
   nothing can be claimed as accessed (FR-2.7).
2. **The person names the jurisdictions** (entity, parent, operating, customer/supplier countries).
   Free-text case jurisdiction is not guessed into country codes.
3. **Deterministic rules** (`app/research/plan.py`, versioned `PLAN_RULES_VERSION`): one group per
   category; reachable sources are planned; discovery-only sources are planned but flagged (P-06);
   licensed, unavailable or down sources and categories with no source are listed as `NOT_AVAILABLE`
   with the reason (FR-2.4). Unknown source types are ignored and named.
4. **P-03 gate on the server** for every run creation (`require_research_allowed`); blocked attempts
   are audited. Permission `research:run` to create, `case:read` to read; no change to ADR 0001.
5. **P-10:** the run stores app, plan rules, policy and registry versions; prompt, model and connector
   versions stay empty until a step actually uses them.
6. **Snapshots:** each step keeps the registry entry as planned, so later registry edits do not
   rewrite what a run was based on.
7. **Idempotency:** the same `idempotency_key` on a case returns the same run.

## Next
Executor with per-step state, timeouts, bounded retries and backoff (FR-2.5); connector-call log
written only by executed calls (FR-2.6); Redis queue and worker; LLM adapter (ADR 0006).
