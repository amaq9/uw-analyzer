# Recording published credit ratings (ADR 0020)

The product does not search for agency ratings. A person, or a Claude Code session working for the person, finds
them and records them on the case with their source. They are information for the underwriter: they never change the
draft outcome or amount.

## In the screen
Open a case, the **Draft recommendation** tab, Step 1, **Published credit ratings**, then **Record a published
rating**. Fill in:

| Field | Notes |
|---|---|
| Agency | Moody's, S&P or Fitch |
| Grade | The agency's own wording: Moody's `Baa2`, S&P or Fitch `BBB+`. The grade must exist on that agency's scale. |
| Outlook, last action, review | As published. Leave "Not stated" if it is not stated. |
| Source address | A secure `https://` address of the page you read. Required. |
| When you read it | Defaults to now. It cannot be in the future. |
| The agency's own words | A short quote, up to 300 characters. Required. |

If nothing can be found, record nothing. The screen then says "No published rating recorded", which is correct and
is not a finding about the company.

## Through the API
`POST /api/v1/cases/{case_id}/published-ratings` (permission `draft:import`) with the same fields:
`agency` (`MOODYS`, `SP`, `FITCH`), `grade`, `outlook`, `under_review`, `change`, `last_action_on`, `rationale`,
`source_url`, `retrieved_at`, `quote`. `GET` returns the latest record for each agency, or every record with
`?latest=false`. Records are append-only.

## Where they show
Step 1 shows them under the financial analysis with a plain-words comparison, adds four rating red flags, and lists
"Published credit ratings" under the other research areas. A draft stores the ratings recorded when it was prepared. A
rating recorded later appears on the screen with a note, and a new analysis includes it in a new draft.

## Researching them (a session)
Search the agency's own pages, the company's investor-relations page or a regulator filing. Record only what a page
states, with the page address. Moody's, S&P and Fitch ratings are often behind a paywall: do not guess from secondary
summaries unless the page quotes the agency, and say so in the quote.
