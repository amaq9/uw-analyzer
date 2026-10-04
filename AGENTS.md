# AGENTS.md — Rules for AI coding agents on UW Analyzer

This repo is built by two AI coding agents working in parallel, directed by the Product Owner:

- **Codex** owns the **front end (UI)**.
- **Claude Code** owns the **back end** and everything else that isn't UI.

Every agent reads this file before starting work, every session. It applies to any other agent added later, too.

## 1. Read first

In this order, before writing code or changing scope:

1. This file.
2. `BRD + PRD/progress-log.md`: current phase, next action, open decisions.
3. `BRD + PRD/rulebook.md`: **binding** working rules, hard invariants, definition of done.
4. `BRD + PRD/compliance-and-documentation.md` and `BRD + PRD/security-handoff.md`.
5. Your own handoff file (section 7).

`BRD + PRD/` is local only and git-ignored, so it isn't in GitHub or in any secondary worktree. If you're working in a separate worktree, read it from the master working copy. The Product Owner will give you the path.

Source of truth for requirements: the BRD and PRD (v1.0, 16 Sep 2026) in `BRD + PRD/`.

## 2. Ownership

| Area | Owner | Notes |
|---|---|---|
| `/web/**`: pages, components, styling, client state, front-end unit tests | **Codex** | Next.js + TypeScript + React |
| `/tests/e2e/**`: Playwright end-to-end tests | **Codex** | Claude Code keeps the API testable and supplies seed data |
| `/api/**`: FastAPI service, auth/OIDC, RBAC, tenant isolation, audit events | **Claude Code** | |
| `/worker/**`: background jobs, research pipeline, LLM and connector integration | **Claude Code** | |
| Database schema and migrations | **Claude Code** | |
| `/infra/**`: Docker, Terraform | **Claude Code** | |
| `.github/**`: CI/CD workflows | **Claude Code** | Codex may *request* front-end CI steps (lint, typecheck, Vitest, Playwright) |
| `.pre-commit-config.yaml`, `.gitignore`, security tooling | **Claude Code** | |
| `docs/api/`: API contract (OpenAPI) | **Claude Code** writes, **Product Owner** approves | The interface between the two sides (section 3) |
| `docs/adr/`, `docs/security/`, `docs/runbooks/` | Author of the decision or change | Product Owner approves |
| `AGENTS.md`, `CLAUDE.md`, `README.md`, `CODEOWNERS` | **Product Owner** | Agents propose changes via PR only |

**Rules:**

- **Never edit files you don't own.** If you need a change on the other side, write it up as a request in your handoff and tell the Product Owner, who routes it.
- **Never edit the other agent's handoff file.**
- If ownership of a path is unclear, stop and ask the Product Owner. Don't assume.

## 3. The API contract is the interface

- The OpenAPI spec in `docs/api/` is the single contract between front end and back end.
- **Claude Code** publishes and versions it. Back-end changes that alter request or response shapes must update the spec in the same PR.
- **Codex** builds against the spec, using mocks generated from it until the real endpoints exist. Don't hand-write API types that drift from the spec; generate them.
- If the UI needs a new endpoint or field, Codex requests it (section 2). Neither agent changes the other side to "make it fit."
- Breaking contract changes need Product Owner approval before merge.

## 4. Hard invariants (from `rulebook.md` §1)

These bind **both** agents. The UI is where several of them are most visible.

- **P-09: no autonomous underwriting decision.** The system never approves, declines, rates, or sets a credit limit.
  - *Back end:* no endpoint returns or records a decision on the underwriter's behalf.
  - *UI:* no "Approve" or "Decline" buttons, no score or traffic light that reads as a credit decision, and no wording that implies the system decided. The underwriter decides.
- **P-01, P-02: no fabricated sources or evidence.** Every claim shown must link to its source.
- **P-03:** entity ambiguity blocks substantive research. The UI must surface it, not hide it.
- **P-04:** "accessed" and "verified" are separate fields. Display them separately and never merge them into one badge.
- **P-05:** verification status is exactly one of the 5 fixed values. No extra UI-only statuses.
- **P-06:** weak or discovery-only sources can't alone verify a material claim.
- **P-07:** material conflicts and ambiguities can't be auto-closed. The UI needs an explicit human action to resolve them.
- **P-08:** completed reports are immutable. Amendments create new versions, and the UI shows version history.
- **P-10:** every run records prompt, model, connector, policy and app versions.

If a request conflicts with any invariant, **stop and explain the conflict before writing code.**

## 5. Git workflow

- **Separate working copies.** Each agent works in its own git worktree, never in a folder the other agent is using. This prevents one agent switching branches under the other.
- **Branch names:** `codex/<short-topic>` and `claude/<short-topic>`. Short-lived, one purpose per branch.
- **Never push to `main`.** Every change goes through a pull request that the Product Owner merges. No direct pushes, no force-pushes, no bypassing branch protection.
- **Small, single-purpose PRs** (rulebook §5). A PR touches only paths its author owns, plus a matching spec or doc update where required.
- **Pre-commit hooks must pass** (gitleaks, semgrep, hygiene). Never skip them with `--no-verify`.
- After a PR merges, sync `main` before starting the next branch.

## 6. Public repo: what never gets committed

This repository is **public**.

- Never commit `BRD + PRD/` or any of its contents, or copies of governance docs at the repo root.
- Never commit secrets, tokens, `.env` files, real customer or entity data, or internal prompts.
- No personal details: names, emails, machine or OS details, local file paths.
- Only a sanitised summary of a handoff goes in the repo (see section 7). Full handoffs stay local.

## 7. Handoffs and status

| Agent | Full handoff (local only) | Shareable copy (in repo) |
|---|---|---|
| Claude Code | `handoff-claude-code.md` (git-ignored) | `docs/handoffs/claude-code.md` |
| Codex | `codex-handoff.md` | `docs/handoffs/codex.md` (recommended) |

- After each task, update **only your own** handoff: what was asked, what changed, tests and scans run, blockers, and next action.
- `BRD + PRD/progress-log.md` is shared. Update it only when the Product Owner asks.
- Use the America/Toronto timezone for dated entries.

## 8. Definition of done

Follow `rulebook.md` §3 and report per §4: what changed, tests run and results, security checks, known limitations, and what the Product Owner should test. "Done" means the tests exist and pass, not that the code compiles.
