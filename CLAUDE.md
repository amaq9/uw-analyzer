# CLAUDE.md

Shared rules for every agent on this repo live in `AGENTS.md`. Read it first; it's imported below.

@AGENTS.md

## Claude Code specifics

- **Your role:** you own the **whole product**: `/web` and `/tests/e2e` (UI and browser tests), `/api`, `/worker`, database and migrations, `/infra`, `.github` workflows, security tooling, and the API contract in `docs/api/`. Do UI work yourself; don't route it to Codex (Product Owner decision, 2026-10-20).
- **Your handoff:** update `handoff-claude-code.md` (local only, git-ignored) after each task. Mirror a sanitised summary in `docs/handoffs/claude-code.md` only when the Product Owner asks for it to be published.
- **Never edit** `codex-handoff.md` or anything under `docs/handoffs/` other than `claude-code.md`.
- **Branches:** `claude/<short-topic>`, always merged via PR. Never push to `main`. You may squash-merge your own PR once every required check has passed; never use admin overrides.
- **Contract first:** when an endpoint changes shape, update the OpenAPI spec in `docs/api/` and regenerate the web types (`npm run api:types` in `web`) in the same PR.
