# Research worker and stuck runs (local)

Research runs are planned in the API, then executed by a separate worker process.

## Run it
```
docker compose -f infra/docker-compose.dev.yml up -d
cd api
uv run python scripts/worker.py          # keeps working until you press Ctrl+C
uv run python scripts/worker.py --once   # works through what is queued, then stops
```
Start a run first: `POST /api/v1/cases/<case>/research-runs/<run>/start`.

## What you will see today
No real connectors exist yet, so every planned step ends `SKIPPED` with "No connector is implemented for
this source, so it was not searched", and the run ends `COMPLETED`. That is correct and honest: nothing was
searched and nothing is shown as accessed.

## A run is stuck
- `QUEUED` for long: the worker is not running. Start it.
- `RUNNING` but the worker was stopped mid-run: known limitation, there is no re-queue endpoint yet.
  Ask Claude Code to reset it (a person decision, recorded in the handoff); finished steps are never
  repeated and steps left `RUNNING` are reset when the run is claimed again.
- `FAILED`: read the steps' `error_class` and the call log
  (`GET .../research-runs/<run>/connector-calls`), fix the cause, then `start` again to resume.

## How to tell it worked
The run is `COMPLETED`, steps are in a finished state, and `connector-calls` lists one row per attempt.

## Real connectors (SEC EDGAR and GLEIF)
1. Register them once: `cd api; uv run python scripts/seed_sources.py` (an administrator can also use
   `POST /api/v1/sources`).
2. Set a contact address the registries can reach you at, then start the worker:
   `CONNECTOR_CONTACT=you@example.org uv run python scripts/worker.py` (needs the Docker storage up).
   Without `CONNECTOR_CONTACT` no connector is enabled and steps are skipped, as above.
3. Plan and start a run (UI, or `scripts/assisted.py plan <case> US` then `start <case> <run>`).
4. Read what came back: `scripts/assisted.py run <case> <run>` lists steps and the call log;
   `scripts/assisted.py snapshot <case> <provenance_ref> <file>` saves the exact material.

Also enabled: `ofac-sdn` (sanctions name screening), `world-bank` (country macro indicators) and `gdelt-news`
(news leads, discovery-only; the index allows one request every 5 seconds and may refuse, in which case the
step ends `FAILED` with `retryable`; run `start` again later to resume).

What each connector does and does not do: SEC EDGAR covers U.S. SEC filers only (Nike yes; a private or
non-U.S. company is not found and the step ends with `permanent:no_unique_match`). GLEIF covers any entity
that has a Legal Entity Identifier. Neither covers adverse news, courts, sanctions or sector outlook.

## Alpha Vantage market news (needs a key, ADR 0023)
The `alpha-vantage-news` connector is enabled only when the worker also has `ALPHA_VANTAGE_API_KEY` set. The key
stays on this computer: it is never written to the repo, a snapshot or the call log. Keep the key file at the repo
root (its name contains `API KEY`, which `.gitignore` excludes) or in your own secret store.

1. Register the source once: `cd api; uv run python scripts/seed_sources.py` (adds `alpha-vantage-news`).
2. Start the worker with the key, in PowerShell:
   ```
   cd api
   $env:CONNECTOR_CONTACT = "your address"
   $env:ALPHA_VANTAGE_API_KEY = "<your key>"
   uv run python scripts/worker.py
   ```
3. Plan and start a run as above. The plan lists `alpha-vantage-news` twice: once under the adverse search
   (news about the company's listed share) and once under country and industry (news for the industry's market
   topic).

What it does and does not do:
- Adverse search: finds the company's listed share by exact name (suffixes such as Inc. ignored). If no listing,
  or more than one in the named countries, matches, the step ends `permanent:no_unique_match`; nothing is
  guessed. Private companies are never found.
- Country and industry: the case's industry must map to one of the provider's topics (technology, retail and
  wholesale, manufacturing, energy and transportation, life sciences, real estate, finance); otherwise the step
  ends `permanent:no_topic`.
- The snapshot keeps the latest 50 articles and the provider's own sentiment labels. Labels are automated scores,
  not findings, and every article is a lead: open and read the publisher's page before relying on it.
- The free key allows 25 requests a day (about 3 per run). When the limit is reached the step ends `FAILED`
  with `retryable`; run `start` again the next day to resume. A refused key ends `permanent:key_refused`.
- If the key's plan does not include the news endpoint (the provider answers "premium endpoint"; true of the
  current key on 2026-10-19), news steps end `permanent:premium_required`. Upgrade the key's plan, or leave the
  key unset so the steps are simply `SKIPPED`.
