# ADR 0005: Draft recommendation for the underwriter, and a human-recorded decision (amends P-09)

- **Status:** Accepted in principle, 2026-10-07 (Product Owner decision). **Build is gated** by the
  conditions in "Gates before it can be built or used", and nothing in this ADR is built yet.
- **Date:** 2026-10-07 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Amends:** invariant P-09 (as worded in `AGENTS.md`, the BRD and the PRD) and ADR 0004 point 1.

## Context
The Product Owner decided that, for the purpose of the project, the outcome of the research and the
financial analysis must end in a recommendation: **approve this amount, do not approve, or decline**.
Until now P-09 said the system never approves, declines, rates or sets a credit limit, because that
boundary is a compliance control: it keeps the product in the "decision support" category and out of
automated credit decisioning (`compliance-and-documentation.md`). The rulebook (section 1 and 7)
requires a conflict with an invariant to be stopped, explained and approved as a documented change.
This ADR is that documented change.

## Decision
1. **Two separate things, never confused.**
   - A **Draft recommendation**: produced by the system for the underwriter, labelled "Draft
     recommendation for the underwriter. Not a decision." It has an outcome (`APPROVE` with an
     amount and currency, `NOT_APPROVE`, or `DECLINE`), reasons tied to evidence, and conditions.
   - An **Underwriter decision**: recorded by a named person who **adopts, changes or rejects** the
     draft. Only this is the decision. It is the only thing that may ever leave the system as an outcome.
2. **What does not change in P-09.** The system never makes the decision itself, never acts on a
   recommendation automatically, never issues or communicates an approval, decline or limit to a
   customer, and never creates a binding commitment. Every outcome needs an explicit human action.
3. **What ADR 0004 still forbids.** Scores, grades, rankings, ratings, probability-of-default numbers,
   traffic lights (green/amber/red), pass/fail badges and "risk levels". Research readiness stays a
   process state with a reason, never a verdict. The recommendation is a **structured outcome with
   reasoning**, not a score. Outcome wording is allowed **only** inside the Draft recommendation and the
   Underwriter decision screens and fields, nowhere else.
4. **Preconditions, enforced on the server.** A draft can be generated only when all hold:
   - the legal entity is resolved (P-03) and no mandatory escalation or unresolved material conflict
     is open (P-07);
   - the research run and the financial analysis are complete, with prompt, model, connector, policy and
     application versions recorded (P-10), and their information gaps disclosed;
   - a **PO-approved, versioned recommendation policy** exists (see 5);
   - evidence rules (P-01, P-02, P-04 to P-06) are satisfied for every material claim the reasons use.
   If a precondition fails, no draft is produced, and the reasons are listed in plain language.
5. **No invented policy.** The system must not guess underwriting appetite. Outcomes and amounts are
   produced by a **versioned recommendation policy** (criteria, thresholds, limit rules) written and
   approved by the Product Owner. The policy version is stored with every draft. The AI may help
   draft the narrative, but its output is untrusted input: schema- and rule-validated, and it cannot
   set the outcome or amount; the policy rules do.
6. **Transparent reasoning.** Every reason links to claims and evidence (AC-08). The draft shows key
   strengths, weaknesses, information gaps, assumptions and conditions, and how the amount follows
   from the policy and the requested exposure.
7. **Human adoption.** The underwriter chooses Adopt, Change or Reject. Changing or rejecting
   needs a written rationale. Amounts above thresholds set in the policy need a second named
   reviewer (the Reviewer role). All actions are audited.
8. **Immutability and records.** The draft, the human decision, rationale, approvers and all version
   identifiers are stored in the report version and become immutable on completion (P-08).
   Overrides create a new version; nothing is edited in place.
9. **Roles.** Draft generation needs a research permission. Recording the decision needs a new
   permission (for example `decision:record`) held by the Underwriter and Reviewer roles only. Adding
   it changes ADR 0001's role table and needs Product Owner approval when it is built.

## Gates before it can be built or used
- **Not before the research and analysis exist.** Targeted at Phase 5, after Phases 2 to 4. Phase 1
  is unaffected.
- **Personal local pilot (ADR 0003):** the Product Owner may build and evaluate it locally on synthetic
  or public data, for evaluation only.
- **Before any other user, real customer decision or hosting:** written **Legal and Compliance review**
  of the recommendation feature in each jurisdiction of use (including rules on automated decision
  making and on creditworthiness assessment, and whether individuals such as owners are assessed as well
  as companies), recorded in a new ADR. The author is not a lawyer and does not assert what the law
  requires.
- **Evaluation before enabling:** a golden-case evaluation suite (including adversarial, conflicting
  and incomplete cases) with release thresholds; consistency testing; monitoring of how often
  underwriters override drafts; a fairness and bias review where individuals are involved.

## Open points for the Product Owner
- Precise meaning of the three outcomes: how `NOT_APPROVE` ("no approve") differs from `DECLINE`
  (for example, not approved now / refer or need more information, versus final refusal).
- The recommendation policy itself (appetite, thresholds, limit rules, who must second-review).
- Phase 5 wording for evidence confidence (ADR 0004 point 6).

## Alternatives considered
- **Option A, human-recorded outcome only (no system draft):** the safest, and the recommended
  default; not chosen by the Product Owner for this project. Its human-decision record is part of this design.
- **Keep P-09 as it was:** rejected by the Product Owner for the project's purpose.
- **A system-final decision (no human step):** rejected; it is the autonomous decision P-09 exists to prevent.

## Consequences
- Enforcement changes from "no decision words anywhere" to "decision words only in the two designated
  places, always labelled, always human-adopted". Tests move from a blanket ban to an **allow-list** of
  exact fields and screens when the feature is built.
- More compliance and evaluation work before real use, and a hard dependency on the Product Owner's
  recommendation policy.
- `AGENTS.md`, the BRD and the PRD (P-09, section 3 and FR-5.x) need matching amendments; `AGENTS.md`
  is proposed by PR for the Product Owner to approve. BRD and PRD are the Product Owner's local documents.

## Rollback
Supersede with a new ADR. Until the feature is built nothing needs to be undone; once built, disabling
generation returns the product to evidence-only plus the human decision record.
