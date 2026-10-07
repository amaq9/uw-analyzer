# Runbook: database migrations

Migrations are Alembic scripts in `api/migrations/versions/`. They run from the `api/` folder and read
the database address from the `DATABASE_URL` environment variable (never commit it).

## Apply (forward)
1. Confirm a recent backup exists (staging and production; not needed for the local dev database).
2. `cd api`
3. Set `DATABASE_URL` for the target environment.
4. `uv run alembic upgrade head`
5. **Check it worked:** `uv run alembic current` shows the newest revision, and the API's `/health`
   still returns `ok`.

## Roll back
1. `uv run alembic downgrade -1` (one step) or `uv run alembic downgrade <revision>`.
2. Check with `uv run alembic current`.
3. Warning: downgrading `0001` **drops the audit table and its history**. Never do this in production.
   For production, roll back by deploying the previous release and fixing forward.

## Local development database
- Start: `docker compose -f infra/docker-compose.dev.yml up -d` (Postgres on port 5432).
- Integration tests use a separate database. Create it once:
  `docker exec infra-postgres-1 psql -U uwanalyzer -d postgres -c "CREATE DATABASE uwanalyzer_test"`
  then set `TEST_DATABASE_URL` to that database. The tests reset it on every run.

## Rules
- Every schema change ships with a migration, a tested rollback, and an entry in the data dictionary.
- Never edit a migration that has been merged; add a new one.
- Test-run the migration against a copy of the staging schema before production.
