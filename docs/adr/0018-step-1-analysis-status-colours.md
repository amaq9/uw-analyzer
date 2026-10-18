# ADR 0018: Status colours on the financial areas in Step 1 (amends ADR 0004 and ADR 0005 decision 3)

- **Status:** Accepted, 2026-10-18 (Product Owner decision in chat, confirmed against the options below).
- **Date:** 2026-10-18 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Amends:** ADR 0004 point 1 and ADR 0005 decision 3, which banned traffic-light colours. `AGENTS.md`
  section 4 repeats the ban and is owned by the Product Owner: the proposed wording is at the end.

## Context
The Product Owner reviewed the case workspace and asked for Step 1 (research and analysis) to be more
comprehensive, following the senior-analyst financial-statement-assessment method, with each financial
area shown as **green = OK, yellow = weak, red = distressed**.

ADR 0004 and ADR 0005 decision 3 forbid green, amber or red status colours anywhere, because a colour
reads as a rating of the company and, next to a draft outcome, as a decision. The rulebook requires a
conflict with an invariant to be stopped, explained and approved as a documented change. The Product Owner
chose to amend the ban for Step 1 only (the other options were: amend it everywhere, or keep words only).

## Decision
1. **Where colours are allowed.** Only on the financial dimensions of the Step 1 analysis report and on the
   consolidated financial findings in that report. Nowhere else. **Amended by ADR 0019:** the dimensions are
   now liquidity, profitability, leverage and cash flow (the four the recommendation policy reads), plus
   efficiency and sector, which is shown with its figures but gets no status because peer data is not
   connected (a status would be a guess).
2. **Three statuses plus one.** `OK` (green), `WEAK` (yellow), `DISTRESSED` (red), and `NOT_ASSESSED`
   (grey) when the data is missing. They are derived on the server from the dimension's finding: Strong or
   Adequate = OK, Concerning = WEAK, Critical = DISTRESSED. The framework's own word is shown beside
   the status ("Concerning") so the two vocabularies are never confused. The recommendation policy reads the
   finding, not the colour (ADR 0019).
3. **Never colour alone.** Every colour comes with its word and a symbol (check, exclamation, cross), so
   it reads in black and white and to colour-blind users. A colour key and a plain-language note say it is
   the analyst's reading of the evidence, "not a score or rating of the company and not the decision".
4. **Still forbidden (ADR 0004).** Numbers, percentages, grades, rankings, probability of default,
   "risk levels", pass/fail badges, and any colour on: the draft outcome and amount, the Underwriter
   decision, the final decision report, research readiness, evidence verification, source reliability,
   the case list or anything outside Step 1. The draft outcome stays in words, in the navy and teal palette.
5. **The red-flag checklist is not coloured status.** Its ten items read "Look closer", "Clear" or "Not
   assessable", are prompts and not pass/fail tests, and use text with a neutral emphasis only.
6. **Reproducible.** The status is stored with the draft (in its analysis report) with the analyzer
   version, so the same figures always give the same statuses and a past draft never changes (P-08, P-10).
7. **Enforcement.** The API contract test keeps outcome words to the designated places; the new report uses
   the neutral field names `status`, `finding` and `consolidated_status`. A web test checks that every
   status chip carries its word, and the colours live in one clearly marked block of the stylesheet.

## Senior-analyst framework: what Step 1 takes from it, and what it leaves out
The Product Owner supplied a JP Morgan-style credit framework (`financial-statement-assessment.zip`, kept
local). Step 1 follows its structure where the project's rules allow:
- **Taken:** an executive summary; five dimensions with three periods of figures (current, prior, two
  before) and a direction; profitability margins and returns; the red-flag checklist (16 items: the
  project skill's ten plus the framework's margin, debt-maturity, free-cash-flow, leverage-and-margin,
  customer-concentration and market-share items, with the ones the figures cannot answer marked "Not
  assessable"); a cash-flow and debt-service section; a revenue-fall sensitivity; strengths, weaknesses,
  what to watch and gaps; and "key concerns, most important first".
- **The sensitivity is arithmetic, not a forecast.** It assumes costs do not fall when revenue falls (the
  worst case) and says so on screen. No other assumption is made.
- **Left out on purpose:** its "Credit Recommendation & Loan Terms" section (approve/decline, amount,
  covenants, pricing, conditions) because P-09 forbids the system from doing that: the draft comes from
  the approved policy and a named person decides; its instruction to "make reasonable assumptions" about
  missing figures, because P-01 and P-02 forbid estimating; peer benchmarks, which are unsourced here and
  indicative only; and "risk ranked by severity with impact and probability", replaced by an ordered list
  of concerns with no severity label, number or probability (ADR 0004 bans rankings and risk levels).
- **Not replaced:** the project's own skill and the policy's inputs stay as they are. The framework's
  Strong/Adequate/Concerning/Critical thresholds were used only for profitability, which is context.

## Alternatives considered
- **Words only (no colour):** the safest reading of ADR 0004; not chosen by the Product Owner.
- **Colours everywhere, including the draft outcome:** rejected as the default. It makes the product look
  like a rating and blurs the line between the analyst's reading and the recommendation.
- **A numeric score per area:** rejected. A number invites comparison and false precision.

## Consequences
- Step 1 can be scanned at a glance, with the figures and the reasons one click below each colour.
- The product now has a three-level colour status on financial areas. This is closer to a rating than before.
  It is kept inside the test-product frame (ADR 0005, test-product status) and the tripwire there applies:
  if the product is ever used for real underwriting or by others, review this ADR again with Legal and
  Compliance.
- Existing drafts made before this change have no analysis report. The screen says so and offers to run the
  analysis again, which makes a new draft version. Nothing already recorded is altered.

## Proposed wording for `AGENTS.md` section 4 (Product Owner to apply)
Replace "no rating, score, traffic light or credit-limit wording" with: "no rating, score or credit-limit
wording, and no traffic-light colours except the OK, Weak and Distressed status on the five financial areas
in the Step 1 analysis report (ADR 0018); research readiness, verification and the draft outcome never use
colour as a verdict."

## Rollback
Supersede with a new ADR and remove the status colours from the report stylesheet block. The stored
`status` values can stay, because they carry words and are harmless without colour.
