# ADR 0003: Personal local pilot (documented exception to the Phase 0 gate)

- **Status:** Accepted, 2026-10-07 (approved by the Product Owner)
- **Date:** 2026-10-07 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Context
The rulebook (section 2) and PRD section 17 say a phase's exit criteria must be met before the next
phase's work merges to `main`. Phase 0's exit criteria include a successful staging deployment, which
needs a cloud or hosting decision still being worked through with IT. The Product Owner's immediate
aim is to use the product alone, on their own laptop, to judge whether it is worth taking further,
before involving cloud hosting or other users.

## Decision
The Product Owner approved this exception, in their words:

> Personal local pilot: Phase 0's staging and cloud items are deferred. Phase 1 onward may merge,
> running on the Product Owner's laptop only. Nothing is deployed or shared. Before anyone else uses
> it, Phase 0's exit criteria and the full security gate must be met.

Concretely:
1. **Deferred, not waived:** FR-0.3 (staging and production environments), FR-0.7 (deploy to staging),
   real identity-provider sign-in, the restricted database account, and the retention, recovery and
   hosting decisions.
2. **Allowed meanwhile:** phases may be built and merged in order (Phase 1, then 2, and so on), running
   locally for one user. Sign-in stays the local test sign-in (`AUTH_MODE=stub`, refused outside
   `APP_ENV` local or test).
3. **Everything else still applies:** all hard invariants (P-01 to P-10), tests, CI and security
   scans, PRs and reviews, the contract-first rule, and definition of done. Only the staging
   deployment requirement is deferred.
4. **Nothing is deployed, shared or exposed to a network.** The API listens on `127.0.0.1` only.
5. **Exit from the pilot (all required before a second person or any real hosting):**
   - Phase 0 exit criteria met, including a successful staging deploy.
   - Real identity-provider sign-in working and the stub path unreachable.
   - Restricted database role in place and ADR 0002's tamper-resistance gap closed.
   - Retention periods, recovery targets and the hosting decision made, and a data-protection check
     on any external service that receives case content (including any AI provider).
   - Product Owner sign-off.

## Cautions recorded
- **Real data:** case data is Restricted under `docs/security/data-classification.md`. The Product
  Owner confirms their organisation's policy allows it on a personal laptop; until then use public
  filings and made-up cases.
- **AI research (Phase 2 onward):** sends text to an AI provider. Even for personal use this needs a
  provider choice and a data-handling check first. No case content is used for model training.

## Alternatives considered
- **Wait for hosting before Phase 1 merges:** safest, but blocks the Product Owner's evaluation on
  an unrelated decision.
- **Develop Phase 1 on unmerged branches:** allowed by the rulebook but builds up hard-to-merge work.

## Consequences
- Staging-only defects (deployment, configuration, real sign-in) will be found later, at the pilot exit.
- Risk is bounded by the single-user, local-only constraint; if that changes, the exit conditions
  above apply first.

## Rollback
Revoke this ADR (supersede it); further phases then stop merging until Phase 0's exit criteria are met.
