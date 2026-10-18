# ADR 0020: Published agency credit ratings as external information (amends ADR 0004)

- **Status:** Accepted, 2026-10-18 (Product Owner decision in chat: option "both", the ratings block in
  Step 1 together with the analyst framework).
- **Date:** 2026-10-18 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Amends:** ADR 0004 (no ratings, scores or grades anywhere). Builds on ADR 0018 and ADR 0019.

## Context
The Product Owner supplied an enhanced analyst skill that also researches the published credit ratings of
Moody's, S&P and Fitch and weighs them with the financial analysis. ADR 0004 bans ratings, scores and grades in
the product and the API contract test blocks the word "rating" in names. The ban exists so that the product never
rates a company itself. An agency's own published opinion is a different thing: it is a fact about what a third
party said, which can be recorded with its source like any other evidence.

## Decision
1. **External information, not our rating.** A published rating is the agency's opinion, shown as such, with the
   agency's name, grade, outlook, date of the last action, stated reasons and a link to the source. The screen says
   it is not this product's rating.
2. **Information only. It never changes the draft.** Ratings are not an input to the recommendation policy, the
   proposed amount or the outcome. A test proves that the same figures give the same outcome and amount with and
   without ratings, and that a strong published rating cannot rescue a distressed company.
3. **Evidence first (P-01, P-02).** A rating is recorded only with its secure (https) source address, the time it
   was read and the agency's own words, and only if the grade exists on that agency's own scale (Moody's Aaa to C,
   S&P and Fitch AAA to D, with SD and RD). The database refuses a record with no source. The system never invents,
   infers or fills in a rating.
4. **Honest about absence.** If nothing is recorded for an agency the screen says "No published rating recorded". That
   is not a finding about the company; most private companies have none.
5. **Words only, no colour.** The status colours of ADR 0018 stay on the financial dimensions. Ratings are not
   coloured, scored or ranked.
6. **The correct scale.** Investment grade is Moody's Aaa to Baa3 and S&P or Fitch AAA to BBB-. The supplied skill
   text puts the line at A3 and A-, a notch too early, so it is not copied.
7. **Recorded by a person or an analyst session.** The product does not search the web by itself. Recording needs the
   same permission as the analyst role (`draft:import`: underwriter, reviewer, or a Claude Code session); reading
   needs `case:read`. Records are append-only: a newer record for an agency supersedes the older one in the analysis
   and the older one stays on record. Audit events record the agency only, never the grade or reasons.
8. **Compared in plain words.** The Step 1 report says whether the published ratings and the financial analysis point
   the same way or differ, and when they differ it lists possible reasons and says neither overrides the other.
9. **Four red flags from the framework**: a downgrade within six months, a negative outlook, speculative grade, and a
   rating under review. They are prompts to look closer, not pass or fail, and read "Not assessable" when nothing is
   recorded.
10. **Reproducible (P-08, P-10).** The ratings recorded when a draft was prepared are stored in that draft's analysis
    report. A rating recorded later does not change an existing draft; the screen says so and offers a new analysis.
11. **Contract allow-list.** `tests/p09.py` gains exactly: the path `/api/v1/cases/{case_id}/published-ratings` and the
    properties `published_ratings` and `ratings_reconciliation`. Nothing else may use the word.

## Main sources (Product Owner, 2026-10-18)
The agencies' own websites are the **main sources** for a published rating: S&P Global (`www.spglobal.com`),
Moody's (`ratings.moodys.com`) and Fitch (`www.fitchratings.com`).

- **Labelled, not forbidden.** Each recorded rating says whether its source address is on the agency's own website
  ("main source") or somewhere else ("secondary source": press, an aggregator, another site). A secondary source is
  still accepted, because the agencies' pages are often behind a subscription or refuse automated access, but the
  screen and the report say so and ask the underwriter to confirm it on the agency's own site.
- **The whole domain is checked**, so a look-alike never counts: `evil-spglobal.com`, `spglobal.com.evil.org`,
  `www.spglobal.com@evil.org` and `fitchrating.com` (without the "s") are all secondary. Another agency's site does not
  count for this agency. The label is always worked out from the address, never taken from what a caller sends.
- **Each agency row links to its site** ("Look up on ...") and the recording form names the three sites.
- **Registered as sources.** The three agencies are in the source registry (ADR 0009) as `credit_rating_agency`,
  class COMMERCIAL, access RESTRICTED_LICENSED, no credential held. The research planner ignores a source type it has
  no connector for, so they add no research steps. The product still does not fetch them; a person or an analyst
  session records what a page states.
- **A rating is current only until the next action.** A newer record for an agency supersedes the older one in the
  analysis, and both stay on record. A draft keeps the ratings recorded when it was prepared.

## Alternatives considered
- **Automatic web search for ratings inside the product:** rejected for now. There is no approved connector, agency
  pages are often paywalled, and a search result is discovery-only (P-06). A person or analyst session records what
  they read, with its source.
- **Let ratings adjust the amount or trigger a decline:** rejected by default. Ratings are another party's opinion,
  often missing, and the Product Owner's policy did not define appetite for them. The policy file records the choice
  (section 2i) and can change in a later version.
- **Do not show ratings at all:** rejected; the Product Owner asked for them.

## Consequences
- The product now stores and displays third-party grades. They can be wrong or stale, so each shows its read time and
  source, and the screen never presents them as ours.
- One more table (`published_ratings`, migration 0015) and one more audited action.
- If ratings are ever to influence an outcome, that needs a new policy version approved by the Product Owner.

## Rollback
Remove the block from Step 1 and stop exposing the endpoints; the stored records are append-only and harmless. The
contract allow-list entries are removed with them.
