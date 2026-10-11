# ADR 0016: Built-in analyzer v1 turns research into findings and a draft recommendation

- **Status:** Accepted, 2026-10-12 (Product Owner: "I want the project to recommend a decision ... test the project's
  ability to analyze the financial statements and all other research areas to come to a recommendation";
  whether the underwriter accepts it is a separate step)
- **Date:** 2026-10-12 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Builds on:** ADR 0005 (draft recommendation, human decision), ADR 0008, ADR 0015 (skills as analyzer, no API key).

## Decision
1. **One action produces the recommendation.** `POST /api/v1/cases/{id}/analysis` (permission `draft:import`) reads the
   case's latest finished research run, applies the written rules in `app/analysis/`, records evidence and claims, and
   submits a draft recommendation through the same validated draft path as any analyst. The result is labelled
   "Draft recommendation for the underwriter. Not a decision." The server's approved policy v1.0 still sets the outcome
   and amount; a named person still decides (ADR 0005). Nothing is decided, sent or committed.
2. **The skill's method, as code.** Figures come from the SEC's structured annual data (only 10-K, USD, a full year or a
   fiscal-year-end balance). The five areas use the same ratio method as the financial-statement-assessment skill (tested
   for exact agreement with its script). Missing tags stay missing and the section is "not assessed"; nothing is estimated.
   Derived figures (for example EBIT from pre-tax income) are listed as information gaps.
3. **Each section is described in words, not numbers (ADR 0004):** Strong, Satisfactory, Needs attention, Weak, with
   reasons, a red-flag list and a trend against the year before (the same rules applied one year back). Thresholds are
   in `app/analysis/assess.py`; headline ones: weak if current ratio under 1.0, negative equity, net debt above 4 times
   EBITDA, interest cover under 1.5x, operating cash flow not positive; needs attention if operating cash flow is below
   net income, free cash flow does not cover dividends and buybacks, receivables grow more than 10 points faster than
   revenue or days outstanding rise by a week. Receivables can never be "strong" because no aging schedule is available.
4. **Consolidated finding follows policy v1.0:** weak only when at least three of the four core sections (balance sheet,
   liquidity, gearing, cash flow) are weak together, which makes `financial_findings_weak` true and the draft a decline;
   strong only when all four are strong; otherwise satisfactory.
5. **Amount proposal (analyst judgement, made explicit and bounded):** start at the whole amount requested; subtract 5%
   for each section that needs attention, 15% for each weak section, and 5% for each piece of missing information (a
   section that could not be assessed, an adverse-information search that is not complete, a sector outlook that is not
   assessed). The policy then maps the result: 80% or more is the full amount, 20% up to 80% is reduced and rounded down,
   under 20% is a decline. The reasons are listed as factors.
6. **Other research areas.** A clean OFAC name search becomes a finding. A possible or exact match means no draft is made:
   a review item is raised for a person (a name match is not proof). The Global LEI register adds an entity finding;
   World Bank data adds a country-level economic finding. News leads are not read and are listed as a gap.
7. **Not covered, and stated in every draft:** the printed 10-K text, notes and auditor's report; adverse news content;
   court records; other sanctions lists; sector-level outlook; private or non-U.S. companies without SEC data (the
   endpoint says what is missing and makes no draft).
8. **Safe to repeat.** Evidence is reused per connector call and a finding with identical text is reused, so running the
   analysis again adds a new draft version but no duplicate findings. The audit event has counts only.
9. **The Claude Code analyst still adds judgement on request** ("analyse case <id>"), using the same stores; the analyzer
   is the repeatable, tested baseline.
