# ADR 0013: Escalations and conflict resolution (Phase 4, slice 1)

- **Status:** Accepted, 2026-10-11 (Product Owner delegated Phases 2 to 5 to Claude Code; ADR 0003)
- **Date:** 2026-10-11 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Decision
1. **Material conflicts cannot be auto-closed (P-07).** A material claim with a reliable contradicting
   source raises a `CONFLICT` escalation automatically, labelled `HUMAN_REVIEW_REQUIRED`, once per open
   conflict. People can raise `MATERIAL_AMBIGUITY` and `OTHER` escalations. Conflicts are raised by the
   system only.
2. **Only a named reviewer closes an escalation** (`conflict:resolve`, existing role table), in writing:
   an explanation of at least 10 characters. For a conflict the reviewer chooses which side prevails and
   names the preferred evidence, which must be linked to the claim on that side (FR conflict engine:
   an explanation is required when preferring evidence). Resolutions are append-only and one per escalation.
3. **The claim follows the person's choice, nothing else.** `SUPPORTING_PREVAILS` lets the claim reach
   `VERIFIED` if the evidence rules are met; `CONTRADICTING_PREVAILS` leaves it `UNVERIFIED`. No evidence
   is removed. The rules module still decides the status (ADR 0012).
4. **New contradicting evidence after a resolution reopens the question:** a resolution counts only if it
   is newer than the newest reliable contradicting link, and a new escalation is raised.
5. **Comparison view:** each conflict returns both sides compared on authority, date and freshness,
   specificity (primary or secondary), independence of origin and data quality (FR source conflict engine).
6. **Case-level count:** `GET /cases/{id}/escalations` returns `open_count`, which the Phase 5 completion
   gate will use (no report completes with open escalations).
7. Tables `escalations`, `escalation_resolutions` (migration 0012), append-only. Audit has ids and the
   outcome only.
