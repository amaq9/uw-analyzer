# ADR 0005: Draft recommendation for the underwriter, and a human-recorded decision (amends P-09)

- **Status:** Accepted, 2026-10-07 (Product Owner decision; Option B confirmed twice). Nothing in this
  ADR is built yet: it depends on the research and analysis phases and on the Product Owner's
  recommendation policy (see "What it depends on").
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
10. **Test-product label.** Every draft recommendation and decision screen, record and export carries a
    visible "Test product" label while the product is a test product (see below).

## What it depends on
- **Technical order.** The research and financial-analysis phases (2 to 4) must exist first, so the
  feature is targeted at Phase 5. Phase 1 is unaffected.
- **The Product Owner's recommendation policy** (decision 5). Without written rules the system would be
  guessing appetite, which is fabrication (P-02 in spirit). This is an input only the Product Owner can supply.
- **Engineering quality, as for any feature (rulebook section 3):** tests, including golden cases
  (conflicting, incomplete and adversarial inputs) and consistency checks, and a way to see how often
  underwriters override drafts.

## Test-product status and the Legal and Compliance gate (Product Owner override)
The author recommended a written Legal and Compliance review before use. **The Product Owner decided
on 2026-10-07 that no Legal or Compliance approval is required, because this is a test product.** That
decision stands for as long as the product is a **test product**, meaning all of the following hold:
a single Product Owner (or Product Owner-controlled test users), synthetic, public or test data, no real
customer underwriting decisions made or communicated using it, and no hosting for others (ADR 0003).

- The product always shows a visible **"Test product"** label next to any draft recommendation or
  decision (decision 10), so nobody mistakes an evaluation output for a real one.
- **Tripwire, recorded and not enforced as a block:** if the product is ever used for real
  underwriting decisions, real customers' data, other business users or any hosting, the test-product
  status ends. Before that, the Product Owner should obtain Legal and Compliance review in each
  jurisdiction of use (including rules on automated decision making and creditworthiness assessment, and
  whether individuals such as owners are assessed) and a fairness review, and record it in a new ADR.
  The author is not a lawyer and does not assert what the law requires.

## Open points for the Product Owner
- Precise meaning of the three outcomes: how `NOT_APPROVE` ("no approve") differs from `DECLINE`
  (for example, not approved now / refer or need more information, versus final refusal).
- The recommendation policy itself (appetite, thresholds, limit rules, who must second-review).
- Phase 5 wording for evidence confidence (ADR 0004 point 6).

## Alternatives considered
- **Option A, human-recorded outcome only (no system draft):** the safest; not chosen by the Product
  Owner for this project. Its human-decision record is part of this design.
- **Keep P-09 as it was:** rejected by the Product Owner for the project's purpose.
- **A system-final decision (no human step):** rejected; it is the autonomous decision P-09 exists to prevent.

## Consequences
- Enforcement changes from "no decision words anywhere" to "decision words only in the two designated
  places, always labelled, always human-adopted". Tests move from a blanket ban to an **allow-list** of
  exact fields and screens when the feature is built.
- A hard dependency on the Product Owner's recommendation policy, and more evaluation work. Legal and
  Compliance review is **not** required while this is a test product; it becomes relevant if the
  product stops being one (tripwire above).
- `AGENTS.md`, the BRD and the PRD (P-09, section 3 and FR-5.x) need matching amendments; `AGENTS.md`
  is proposed by PR for the Product Owner to approve. BRD and PRD are the Product Owner's local documents.

## Rollback
Supersede with a new ADR. Until the feature is built nothing needs to be undone; once built, disabling
generation returns the product to evidence-only plus the human decision record.
