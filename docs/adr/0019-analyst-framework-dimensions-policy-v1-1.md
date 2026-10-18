# ADR 0019: The analyzer and Step 1 follow the analyst framework; recommendation policy v1.1

- **Status:** Accepted, 2026-10-18 (Product Owner decision in chat: "I want this skill to be used in the
  analyzer and Step 1 ... if you need to update the policy v1.0 then proceed I am authorizing you").
- **Date:** 2026-10-18 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Amends:** ADR 0016 (built-in analyzer), ADR 0018 point 1 (which areas carry a status colour), and
  supersedes recommendation policy v1.0 with v1.1. The policy text is private and local-only; this ADR
  records the structure, as the code does.

## Context
The analyzer and Step 1 were built on the project's five-area method (balance sheet, liquidity, gearing,
receivables, cash flow) with profitability as context. The Product Owner supplied a senior-analyst credit
framework with five dimensions (liquidity, profitability, leverage, cash flow, efficiency and sector), its
own levels (Strong, Adequate, Concerning, Critical), thresholds and output order, and asked for it to be used in
the analyzer and in Step 1. The recommendation policy v1.0 read the old areas, so using the framework for Step 1
only would have left two sets of findings that could disagree on the same screen.

## Decision
1. **One set of dimensions drives both what Step 1 shows and what the policy reads.** The four core
   dimensions are **liquidity, profitability, leverage and cash flow**. **Efficiency and sector** is shown
   with its figures but is never assessed (no peer, market-share or customer data is connected) and never
   changes the outcome or the amount. The balance-sheet and receivables figures are kept as supporting
   metrics and red flags inside leverage and efficiency.
2. **Levels use the framework's thresholds.** Each dimension is Strong, Adequate, Concerning or Critical,
   decided by its worst available metric (one critical metric is not offset by a good one). Missing figures
   make a dimension "not assessed"; nothing is estimated (P-01, P-02). The thresholds appear on screen as
   indicative reference ranges, not verified peer data.
3. **Status colours (ADR 0018) now attach to these dimensions:** Strong and Adequate are OK (green),
   Concerning is Weak (yellow), Critical is Distressed (red). Profitability is no longer context only; it is core.
4. **Recommendation policy v1.1.**
   - Decline when at least three of the four core dimensions are Critical (v1.0: weak balance sheet,
     liquidity, gearing and cash flow together).
   - The full-approval test reads liquidity and profitability, and leverage and cash flow (v1.0: balance
     sheet and liquidity, and gearing and cash flow).
   - The amount reductions keep their fixed shares: a Concerning core dimension 5% of the amount requested, a
     Critical one 15%, and 5% for each piece of missing information.
   - **Unchanged:** the 20% and 80% bands, rounding down, the decline findings, the entity rules, and that a
     named person decides.
5. **Versioning (P-10).** The new policy version is `1.1` and is stored with every draft. Drafts made under
   `1.0` keep that version and remain readable; new drafts must carry `1.1`, and the analyzer is version `2`.
6. **What was not adopted from the framework** (see ADR 0018): its own approve/decline recommendation and loan
   terms, assumptions about missing data, unsourced peer benchmarks, and severity ranking with impact and
   probability.

## Alternatives considered
- **Step 1 follows the framework, the policy stays on v1.0:** safe for amounts, but two classifications would
  appear on the same screen. Rejected once the Product Owner authorised a policy change.
- **Keep both sets of findings, side by side:** rejected as confusing for the underwriter.

## Consequences
- Step 1 and the draft amount can never disagree, because they read the same findings.
- Amounts for the same figures can differ from v1.0 drafts (profitability now counts, the balance sheet and
  receivables no longer have their own findings). Old drafts are unchanged.
- Colour now sits on a dimension that feeds the draft (profitability). It stays inside Step 1 and always carries
  its word (ADR 0018).
- More fixed thresholds are now in code. They are the framework's own and are tested one by one.

## Rollback
Supersede with a new ADR and a policy version that points the core dimensions back at the old areas. Stored
drafts keep the version they were made under.
