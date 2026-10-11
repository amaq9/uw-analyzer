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
