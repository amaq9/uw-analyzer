# ADR 0021: Quality review: notes of the filing, stress test, check wording, "UW Analyzer recommendation"

- **Status:** Accepted, 2026-10-18 (Product Owner instruction in chat after a quality review of the live Nike case,
  with full authority to change any rule needed).
- **Date:** 2026-10-18 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Amends:** ADR 0005 and `AGENTS.md` section 4 (the label of the recommendation); ADR 0018 (Step 1 wording).
  Does not change the recommendation policy (v1.1), the amount, the outcome or any invariant.

## Context
The Product Owner reviewed the Nike case and found: (1) an assessment card said "This is a judgement" and "No
evidence is linked" although it comes from audited figures; (2) how EBITDA and other figures were defined was listed
under Gaps; (3) the analyzer did not read the notes to the financial statements or the auditor's report; (4) a revenue
fall of 10% was shown cutting operating cash flow from USD 2.87bn to -USD 1.77bn; (5) the other prompts were worded
"Clear" instead of saying whether the threshold was crossed; (6) the UI called the analyzer's output a "draft
recommendation", though the UW Analyzer is the one making it; (7) the comparison with the real decision should read
"UW Analyzer versus actual decision".

## Decisions
1. **An assessment shows the facts it rests on.** The evidence tab lists, under a rule-based assessment, each fact it
   rests on with that fact's verification and linked sources. The wording is "an assessment worked out by the written
   rules from the facts it rests on", never "a judgement". The classification stored (`INTERPRETATION`) and the five
   verification statuses (P-05) are unchanged. The figures' evidence now carries the public SEC filing address, and a
   re-run links better evidence to an existing claim instead of leaving it without.
2. **Definitions are not gaps.** `AnalysisReport.definitions` holds how figures were defined (EBIT, EBITDA, net debt,
   debt to equity, free cash flow, and any derived figure). Gaps hold only missing information. Older drafts that
   carried "Figure derived" in their gaps are split the same way on screen.
3. **The notes and the auditor's report are read.** The SEC retrieval also keeps the newest 10-K's main document
   (hash-checked snapshot; a failure to fetch it never fails the figures). The analyzer reads it by text search and
   reports, per topic, **the filing's own sentences**: going concern, auditor's opinion and firm, change of auditor,
   covenants, customer concentration, committed facilities, internal control, legal proceedings, allowance for credit
   losses, subsequent events. A topic is a concern only when a sentence **states** the adverse fact; hypothetical
   risk-factor language ("could", "may", "if") never raises one. A topic the filing does not discuss is never read as
   clear. The three checklist items that need the text (going-concern/covenant/auditor, customers above 50%,
   covenant violations) are answered from it, and are not assessable when the filing was not read. This is
   information only (P-09): it never changes the amount or outcome, and a stated concern is shown as a key concern.
   The analyst skill now requires reading the notes (and the auditor's report) before finalising.
4. **The stress test is corrected.** The old table assumed that every dollar of lost revenue was a dollar of lost
   profit and ignored tax. That is arithmetic for an extreme case, not a plausible downside. The main rows now let
   the cost of sales fall with sales (only the gross profit on the lost revenue is lost; operating expenses stay) and
   let tax fall with profit only while profit stays positive, using the tax rate the company actually paid. The old
   case remains as a separately labelled "extreme" row. The note states the break-even fall in revenue. Without gross
   profit only the extreme case is shown, and says so. Working capital release and management action are ignored and
   the note says so.
5. **Checks say whether the threshold was crossed.** Each check's result is worded by the server from the check:
   "Above threshold" / "Not above threshold" (or "Below" / "Not below") for limits, "Condition met" / "Condition not
   met" for the rest, "Not assessable" when it cannot be checked. Colours: red when the line is crossed, green when it is
   not, grey when not assessable. (The instruction read "above threshold in green"; red for a crossed line and green for
   not crossed is used so that colour keeps meaning "good" and "bad" as everywhere else in Step 1. One word flips it.)
6. **"UW Analyzer recommendation".** The user-facing label of the former "Draft recommendation" is "UW Analyzer
   recommendation" throughout the UI, the API notice text and the documents. It is still a recommendation only: the
   notice keeps "Not a decision", and only the named person's recorded **Underwriter decision** is the decision.
   API paths and field names (`draft-recommendations`, `draft`) are unchanged so the contract does not break.
7. **UW Analyzer versus actual decision.** The final decision report opens with the analyzer's recommendation and the
   actual decision side by side, with whether they match (same outcome and amount, same outcome with a different
   amount, different outcome, or set aside). The overview page carries the same comparison across cases.

## Consequences
- `AGENTS.md` section 4 and ADR 0005 still use the older wording. The Product Owner owns `AGENTS.md`; the new label
  is proposed there by this ADR.
- Real filings word things in many ways. The reader quotes what it matched so a person can judge it, and it is
  conservative (it reports "for you to read" rather than guessing). Tests use made-up filings with the wording real
  filings use, including the risk-factor boilerplate that must not raise a concern.
