# ADR 0023: Alpha Vantage market news, the first connector that needs a key

- **Status:** Accepted, 2026-10-19 (Product Owner asked for the Alpha Vantage market news API to be added)
- **Date:** 2026-10-19 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Amends:** ADR 0015 (connectors so far were free and keyless).

## Context
The adverse search and the industry outlook rely on `gdelt-news` for news leads, and the GDELT index often
refuses requests (ADR 0015 addendum). The Product Owner holds an Alpha Vantage key whose `NEWS_SENTIMENT`
endpoint returns recent articles for a listed share or a market topic, with the provider's own sentiment labels.

## Decision
1. **New connector `alpha-vantage-news`** (`app/research/alpha_vantage.py`), registered as source type `news`,
   class `COMMERCIAL`, access `DISCOVERY_ONLY`, auth `CONFIGURED`. Being discovery-only, it can never verify a
   material claim by itself (P-06); its articles are leads to be read at the publisher.
2. **Adverse search:** the company's listed share is found with Alpha Vantage's symbol search, using an exact
   match on the normalised name, equities only. Listings of the same name in several markets are narrowed to the
   run's named countries; if not exactly one remains, the call ends `permanent:no_unique_match` (P-03, never
   guess). The latest 50 articles for that share are kept.
3. **Country and industry:** the case's industry maps to one of the provider's fixed topics through a short,
   explicit word list. An industry that does not map ends `permanent:no_topic`; nothing is guessed.
4. **The key** comes only from the worker's environment (`ALPHA_VANTAGE_API_KEY`). Without it the connector is
   not created and the plan's steps are `SKIPPED`, as for any source with no connector. The key is sent only in
   the request address to `www.alphavantage.co`, and every address saved in a snapshot has it removed. Error
   codes are fixed strings, never the provider's text. A test checks that no stored object contains the key.
5. **Snapshots** keep the exact symbol-search and news responses, plus a manifest with what was searched, the
   article count, the number of articles the provider labelled bearish for the company's own share, and the
   limitations. The count is the provider's automated label, reported as such, not a finding.
6. **Refusals:** the provider answers HTTP 200 with a message when it refuses. A rate-limit message is retryable
   (the executor backs off; a run that still fails resumes with `start`); a refused key (`key_refused`) or an
   endpoint the key's plan does not include (`premium_required`) is permanent.

## Alternatives considered
- **Add it to `screening_connectors.py`:** that module is documented as free and keyless; a separate module keeps
  the key handling in one place.
- **Resolve the share symbol through the SEC ticker list:** a second host and U.S. filers only; the provider's own
  search keeps the connector on one host.
- **Free-text keyword search for adverse terms:** the endpoint has no keyword search; the provider's labels are
  kept as reported, and reading the articles stays with the analyst and the underwriter.

## Consequences
- Searching sends the company name and share symbol to Alpha Vantage, a commercial provider. Uploaded documents
  and policy text are not sent.
- **Live check, 2026-10-19:** the symbol search worked with the Product Owner's key and found Nike's U.S. share
  (`NKE`, listed as "Nike Inc - Class B", which is why share-class labels are ignored when matching). The news
  endpoint answered "premium endpoint" for that key, so news steps end `permanent:premium_required` until the key's
  plan includes `NEWS_SENTIMENT`. Nothing is shown as accessed in that case.
- The free key allows 25 requests a day (about 3 per run), so it suits the local pilot, not volume use.
- Private companies have no listed share and are not found. The built-in analyzer does not read news snapshots
  yet; as with GDELT, the analyst session reads them.
- First keyed connector: the pattern (environment variable, never stored, test that the key is absent) is the one
  to follow for later licensed sources until a managed secret store is chosen with hosting.

## Rollback
Unset `ALPHA_VANTAGE_API_KEY` (steps become `SKIPPED`), or mark the source `TECHNICALLY_UNAVAILABLE` in the
registry (steps become `NOT_AVAILABLE` with the reason). Removing the module and the seed entry undoes the code.
