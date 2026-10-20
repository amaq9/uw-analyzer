# ADR 0024: The UW Analyzer Decision Summary replaces the final decision record

- **Status:** Accepted, 2026-10-20 (Product Owner instructions in chat).
- **Date:** 2026-10-20 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Builds on:** ADR 0018 (final report), ADR 0022 (executive summary). No change to the recommendation policy (v1.1),
  the amount, the API or any invariant.

## Context
The printed final decision record listed the underwriter's working points ("Points to settle first") next to the
decision. The Product Owner wants a page that can be printed and shown to the chief executive.

## Decisions
1. **One page for the chief executive.** The Final decision tab shows only the **UW Analyzer Decision Summary**:
   the underwriter's decision and how it compares with the request and the UW Analyzer recommendation, why the amount
   is below the request, a short summary, eight key figures against the year before, the standing of the four core
   dimensions, strengths, risks, what the rating agencies say, what happens if sales fall, and one line on what the
   review did not cover. It fits on one printed Letter or A4 page.
2. **The full decision record is removed** for all decision reports. The points to settle stay on the UW Analyzer
   recommendation tab (Step 2), where the underwriter works through them before deciding.
3. **Built only from the stored analysis**, so it says nothing the recommendation does not, and older recommendations
   print without being analysed again. Strengths are the core dimensions rated OK with their key measures, clean
   annual-report findings (audit opinion, going concern, covenants, internal control), a clear sanctions name search
   and a confirmed legal entity. Risks are the warning signs that fired. Those about the rating agencies are shown once,
   under the agencies.

## P-09
The page is named after the product, but the decision on it is always labelled **Underwriter decision** with the
person's name. Before a decision is recorded the tab shows no summary at all.
