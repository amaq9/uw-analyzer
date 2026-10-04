# CLAUDE.md

Shared rules for every agent on this repo live in `AGENTS.md`. Read it first; it's imported below.

@AGENTS.md

## Claude Code specifics

- **Your role:** you own the **back end and everything that isn't UI**: `/api`, `/worker`, database and migrations, `/infra`, `.github` workflows, security tooling, and the API contract in `docs/api/`. **Codex owns `/web` and `/tests/e2e`. Never edit them.**
- **Your handoff:** update `handoff-claude-code.md` (local only, git-ignored) after each task. Mirror a sanitised summary in `docs/handoffs/claude-code.md` only when the Product Owner asks for it to be published.
- **Never edit** `codex-handoff.md` or anything under `docs/handoffs/` other than `claude-code.md`.
- **Branches:** `claude/<short-topic>`, always merged via PR. Never push to `main`.
- **Contract first:** when an endpoint changes shape, update the OpenAPI spec in `docs/api/` in the same PR, so Codex can build against it.
