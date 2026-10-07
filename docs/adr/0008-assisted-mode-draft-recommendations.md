# ADR 0008: Assisted mode: draft recommendations imported from an analyst session

- **Status:** Accepted, 2026-10-07 (Product Owner: "yes", to assisted mode); **partly built** (see "Build status")
- **Date:** 2026-10-07 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Builds on:** ADR 0003 (personal local pilot), ADR 0005 (draft recommendation, human decision),
  ADR 0006 (Claude with versioned method artifacts), recommendation policy v1.0 (private, local only).

## Context
The Product Owner wants to see how the interface looks, operates and decides on limits, without first
creating an Anthropic API key. The financial-statement skill runs inside Claude Code, not inside the
product. ADR 0006 already makes the AI provider swappable behind a neutral interface. The product
(Phases 2 to 4) cannot yet research and analyse a company by itself. This ADR records a documented
exception to the phase order (like ADR 0003): bring forward the draft recommendation, the human decision
and the agreement view, and let an analyst session (Claude Code, using the skill and the policy) supply
the analysis in the meantime.

## Decision
1. **Assisted mode.** For a case, the Product Owner asks Claude Code to analyse it. Claude Code reads the
   uploaded documents, applies the financial-statement skill and the approved policy, may search the web
   (citing sources), and submits a **draft recommendation** through the same validated path the
   automatic pipeline will use later. When the Anthropic API pipeline exists, it replaces the analyst
   session behind the same interface; nothing on screen changes.
2. **The server decides the outcome and amount, never the author.** The author supplies findings, reasons
   with evidence, any verified decline findings, whether the consolidated financials are weak, and the
   AI's proposed amount. The server applies **policy v1.0**, encoded as deterministic rules
   (`app/recommendation/policy.py`): entity not confirmed, a verified insolvency, sanctions, fraud or
   regulatory action, or going-concern doubt means decline; weak consolidated financials mean decline;
   otherwise the proposed amount against the amount requested: 80% or more is the full requested amount,
   20% up to 80% is a reduced amount **rounded down** to the nearest 1,000, below 20% (also after rounding)
   is decline, and an amount above the request is refused.
3. **Evidence is checked.** Every reason and finding carries evidence. A document reference must be a real
   upload of this case; a web source needs a secure address, the date it was read and the quoted words.
   An unverified material adverse finding is not a decline: it blocks the draft until a person resolves
   it (P-06, P-07).
4. **Honest labels and records.** Every draft shows "Draft recommendation for the underwriter. Not a
   decision.", "Test product", the policy version, the source (a Claude Code session, model, skill
   version) and "Payment behaviour was not assessed (data not used in this product)." Drafts are
   append-only: a new analysis creates a new version, and nothing is overwritten (P-08, P-10).
5. **The entity gate.** A draft can be made only when the legal entity is resolved, or when a person has
   recorded that it could not be confirmed or found (a decline, with no research). Both are human actions.
6. **Permissions (changes ADR 0001's role table; flagged for Product Owner approval).** Two new
   permissions: `draft:import` (underwriter, reviewer, service) and `decision:record` (underwriter,
   reviewer). Research analysts, auditors and administrators hold neither.
7. **The human decision** (next piece): the underwriter adopts, changes or rejects a draft; changing or
   rejecting needs a written reason; one decision per draft; append-only. **The agreement view** compares
   the AI's draft with the underwriter's own outcome and amount, and is how the Product Owner tests the
   product.
8. **No second review** (policy section 2g).
9. **Data handling.** In assisted mode the documents and web pages read, and the policy text, pass through
   Claude Code to Anthropic, exactly as in this conversation. Payment data is out of scope and never used.
   Audit events carry ids and codes only, never outcomes, amounts, reasons or file names.

## Build status
- **Built (this PR):** the policy rules (with boundary tests), draft import with validation, document
  evidence checks, drafts store (append-only), list and read endpoints, the entity "could not be
  confirmed" action, the P-09 allow-list tests, tenant isolation and audit.
- **Next (own PRs):** the underwriter decision endpoints and the agreement view; a local helper so Claude Code
  can read a case and its documents and submit a draft without needing a sign-in token; the runbook for
  assisted mode; Codex's screens for all of it.

## Alternatives considered
- **Wait for the API pipeline:** safest to the phase order, but the Product Owner sees the outcome later.
- **Let the author supply the outcome:** rejected; the policy would depend on the author's care.
- **Skip server-side evidence checks for assisted drafts:** rejected; the same checks must hold when the
  automatic pipeline replaces the analyst session.

## Consequences
- The analyst step is manual (the Product Owner asks each time) and its sector outlook and adverse search
  are cited by the analyst but not independently verified by the system.
- Part of Phase 5 exists before Phases 2 to 4. Those phases still need to be built; assisted mode does not
  replace them.
- Allow-listed decision wording (ADR 0004's tests) now lives in `tests/p09.py`; changing that list needs a
  new ADR.

## Rollback
Remove the draft endpoints; `alembic downgrade 0005` drops `draft_recommendations`. Phases 1 features are
unaffected.
