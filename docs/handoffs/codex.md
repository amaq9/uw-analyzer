# Codex Front-End Handoff

## Ownership

- Codex implements front-end work under `/web/**` only, following the Product Owner's narrower assignment.
- Back-end, infrastructure, CI/CD, shared governance, and Claude Code's handoff remain outside Codex's ownership.
- Work uses a separate Git worktree and short-lived `codex/<topic>` branches.

## Current Status

- No front-end implementation task is active.
- The Codex working branch was synchronized with `origin/main` before this handoff update.
- Repository and local governance instructions have been reviewed.

## Completed Work

- Established the isolated Codex working-copy workflow.
- Confirmed `AGENTS.md` is available and readable.
- Moved the publishable handoff to this sanitized repository document; the detailed working handoff remains local only.

## Verification

- Confirmed the working branch matched the latest fetched `origin/main` before creating this update.
- Confirmed no Claude-owned implementation or handoff files were modified.
- Pre-commit checks must pass before this change is pushed.

## Blockers and Risks

- The `/web` application remains an empty scaffold pending an explicitly assigned front-end task.
- API-dependent UI work must use the versioned OpenAPI contract and request back-end changes through the Product Owner.

## Next Action

Before the next implementation task, fetch and merge the latest `origin/main`, then implement only the smallest approved `/web` slice with appropriate tests.
