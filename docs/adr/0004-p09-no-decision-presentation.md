# ADR 0004: No decision, rating, score or traffic-light presentation anywhere (P-09)

- **Status:** Accepted, 2026-10-07 (stated as a decision by the Product Owner). **Point 1 is amended by
  ADR 0005**, which allows a labelled Draft recommendation and a human-recorded Underwriter decision
  in two designated places only. Everything else here stands.
- **Date:** 2026-10-07 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Context
Invariant P-09 says no feature may issue an autonomous underwriting approval or decline, or a binding
commitment. The human underwriter decides. P-09 has so far been enforced in the API (no decision
permission, endpoint or field, with tests) and described for the UI in `AGENTS.md` section 4. The Product
Owner asked for the presentation side of the rule to be recorded as a decision outcome of the project,
in these words:

> P-09: no approve, decline, rating, score, traffic light or credit-limit wording or UI anywhere.
> Never present research readiness as a score or a decision.

## Decision
1. **No decision language or UI, anywhere**, except the two designated places in ADR 0005 (a
   labelled "Draft recommendation for the underwriter" and the human "Underwriter decision", both
   not built until the later phase and gated there). The product (UI, API, reports, exports, emails, help text,
   documentation shown to users, and the AI agent's output) must not contain wording or controls that
   approve, decline, rate, score, grade, rank, set or suggest a credit limit, give a traffic light
   (green, amber, red or equivalent), or otherwise read as a credit decision or recommendation to
   act on an account.
2. **Research readiness is a process state, not a verdict.** `research-readiness` says whether
   research can start and, if not, what a person must do (for example "Research cannot start until a
   person chooses the one exact legal entity"). It is shown as plain wording ("Research can start" or
   "Research is blocked") with the reason, never as a score, percentage, grade, colour-coded signal,
   badge that reads as pass or fail, or ranking, and never as an approval or clearance.
3. **No status can read as a decision.** Statuses stay the fixed values the protocol defines
   (P-05 for verification; the case statuses in the data dictionary). No UI-only statuses are added.
4. **Forbidden words and forms (non-exhaustive):** approve, approved, approval, decline, declined,
   reject (of a customer), accept (of a customer), rating, rated, score, scoring, grade, rank,
   risk level, recommend (an account action), pass, fail, credit limit, limit set or suggested,
   traffic light, red, amber, green used as risk signals.
5. **Allowed, with care:**
   - Statements that the system does **not** decide ("The system informs. The underwriter decides.").
   - Facts reported **from a source and attributed to it**, for example a credit rating disclosed in a
     company's filing, shown with its source and date as evidence. It is never presented as ours.
   - The requested **exposure and terms entered by the user** about the case (these are inputs).
6. **Research confidence (PRD FR-5.3) is not a credit rating.** When Phase 5 shows how much confidence
   the evidence supports (identity, financial, payment, ownership, industry, adverse, overall), it is
   labelled **"evidence confidence"** (levels High, Moderate, Low, with the explanation), never as a
   "rating" or "score", never colour-coded as a traffic light, and never rolled up into a credit view
   beyond what the protocol requires. **Open point for the Product Owner before Phase 5:** confirm this
   wording, because FR-5.3 as written says "confidence ratings".

## How it is enforced
- **API:** no decision permission exists and a test fails if one appears
  (`test_no_permission_can_make_an_underwriting_decision`); a test fails if any API path or schema
  property name suggests a decision, score or rating
  (`test_no_case_field_or_path_can_carry_a_decision` and the contract path test).
- **After ADR 0005 is built:** these tests change from a blanket ban to an allow-list of exact
  fields and screens; scores, ratings, grades, rankings, traffic lights and readiness-as-verdict stay
  forbidden.
- **UI (Codex):** a front-end test renders each screen and fails if any forbidden word appears,
  except in an explicit statement that the system does not decide or in attributed source facts; and
  no traffic-light colouring is used for readiness or status. Review of any new screen checks this.
- **Review:** every PR description states that P-09 was checked. A conflicting request is stopped and
  explained before any code is written (rulebook section 1).
- **Documentation:** `docs/research-protocol-mapping.md` maps P-09 to these tests.

## Alternatives considered
- **Leave P-09 as an API-only rule:** the UI is where wording and colours are most visible, so
  the risk would be left unguarded.
- **Allow a neutral "readiness score" for sorting work queues:** rejected; any score invites being read
  as a credit signal.
- **Allow colour cues for readiness (green and red):** rejected as a traffic light.

## Consequences
- The UI uses plain wording and reasons instead of badges that read as pass or fail.
- Some natural business words (rating, score, recommend, approve) are off limits in the product.
- Source-attributed third-party ratings remain allowed as evidence, which needs a clear "reported by
  [source]" presentation.
- Phase 5 wording for confidence needs the Product Owner's confirmation (point 6).

## Rollback
Supersede this ADR with a new one that states what changes. This rule serves a compliance control
(`compliance-and-documentation.md`), so loosening it needs Product Owner and compliance agreement.
