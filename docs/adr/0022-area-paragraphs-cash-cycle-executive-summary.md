# ADR 0022: Area paragraphs, cash conversion cycle, executive summary, dimension order

- **Status:** Accepted, 2026-10-19 (Product Owner instructions in chat).
- **Date:** 2026-10-19 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Builds on:** ADR 0018, 0019, 0021. No change to the recommendation policy (v1.1), the amount or any invariant.

## Decisions
1. **Why each dimension stands where it does.** Every financial dimension carries a short paragraph built from the
   measures the rules already used (`AreaReport.summary`). It names the weakest measure (the one that sets the
   rating), its value against its reference, the measures that are better, what moved against the year before and the
   rating's effect on the proposed amount (5% for concerning, 15% for critical, none otherwise). The same measures set
   the finding, and a test proves the measures and the finding always agree.
2. **Cash conversion cycle.** A new Step 1 section shows DSO, DIO, DPO and CCC (= DSO + DIO - DPO) for up to three
   periods, with the movement against the year before and whether it helps cash. Year-end balances are used. A company
   with no inventory shows "No inventory reported" for DIO and the cycle is DSO less DPO. Missing payables or cost of
   sales are stated, never estimated. Cost of sales and trade payables are new figures (SEC tags, and statement upload
   lines). Context only: it sets no finding and no amount.
3. **Executive summary for the decision-maker.** The UW Analyzer recommendation (Step 2) now carries a summary written
   for a chief executive: the recommendation and amount with what reduced it, how the four core dimensions stand, the
   financial position in numbers, the cash cycle, what the agencies say, screening (OFAC, entity register, news,
   courts, country), the annual report notes and auditor, what happens if sales fall, what is not known, and the points
   to settle first. It is built from the analysis only, so every sentence traces to Step 1. The outcome it states is the
   one the server's pure policy function gives for the same inputs, computed before the draft is stored. The one-page
   final report uses its headline and points. Step 1's own summary is now called "Financial summary".
4. **Order and name.** The dimensions read profitability, liquidity, balance sheet and leverage, cash flow, then
   efficiency and sector. "Leverage" is titled "Balance sheet and leverage". API keys (`leverage`, ...) are unchanged.

## Contract
Additive: `AreaReport.summary`, `AnalysisReport.cash_cycle`, `AnalysisReport.executive_brief` (field
`points_to_settle`, named to stay clear of the decision-wording contract test).

## Addendum, 2026-10-19 (Product Owner quality review of the first build)
5. **The cash conversion cycle is rated like the financial dimensions.** It carries the same signal (OK, weak,
   distressed, not rated), a left-edge colour, a "Why this standing, and what to do" paragraph and flags. The skill
   lists a deteriorating cycle as a cash-flow risk indicator, so it is judged on **movement against the year
   before**, by the weakest of: the change in the cycle, in days sales outstanding, in days inventory outstanding
   (not for a company with no inventory), and a large change in days payables (more than 15 days later may mean
   suppliers are stretched; more than 10 days sooner, that suppliers tightened terms). For the cycle, sales and
   inventory days: no longer (a day at most) is strong, up to 5 days longer adequate, more than 5 concerning, more
   than 15 critical. The recommendations are specific to what moved (ask for the receivables ageing; ask what is behind
   a stock build-up; ask whether suppliers are being stretched or have tightened). **Context only**: the policy
   reads the four core dimensions, so it never changes the amount. Making it a fifth core dimension would need a
   policy change and is not part of this decision.
6. **The agencies' stated reasons are in the executive summary.** For each agency the summary gives the grade,
   outlook, date, whether it was a downgrade, and the agency's own reason for the rating and outlook (as recorded
   with the rating), naming where it was reported. A rating taken from the press still carries the agency's reasons,
   labelled as from a secondary source with a prompt to confirm on the agency's own site. A rating recorded without a
   reason says so.
7. **The five dimensions on the Skills page** read in the required order: Profitability, Liquidity, Balance sheet and
   leverage, Cash flow, Efficiency and sector.
