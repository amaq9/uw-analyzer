# Codex Front-End Handoff

Last updated: 2026-10-07 (America/Toronto)

## Ownership

- Codex owns `/web/**`, `/tests/e2e/**`, and this published handoff.
- Backend, worker, infrastructure, CI/CD, the API contract, and Claude Code's handoff remain outside
  Codex's ownership.
- Frontend work uses isolated worktrees, short-lived `codex/<topic>` branches, generated OpenAPI
  types, and small single-purpose pull requests.

## Completed work

### Frontend foundation and Skills

- PR #12 established the responsive Next.js shell, overview, navigation, sign-in presentation,
  truthful empty states, and core invariant tests.
- PR #19 added the Financial Statement Assessment information architecture and safeguards. Execution
  remains disabled because no approved backend skill contract exists.

### API connection foundation

- PR #25 added contract-generated TypeScript declarations, validated API base-URL configuration,
  safe standard-error handling, and development-only token sign-in through `/api/v1/me`.
- Tokens remain in React memory only. They are not persisted in browser storage, URLs, logs, or
  analytics.
- Enterprise SSO remains disabled. The local token form is excluded from production builds.
- Safe error messages and request IDs are shown without exposing raw responses, tokens, or stack
  traces.

### Contract synchronization

- PR #27 refreshed the generated declarations for cases, entity candidates, explicit entity
  resolution/reopen, and research readiness.
- `npm run api:types` is the canonical generation command; the previous command remains an alias.
- A stale-types test regenerates into a temporary directory and compares the result with the
  committed declaration.
- PR #31 received a single-file frontend commit refreshing the declarations for secure document
  upload endpoints. No upload UI was added.

## Verification status

- Latest API-type refresh: lint passed, TypeScript passed, 12 tests passed, and the production build
  passed.
- The stale-types test passed.
- Pre-commit hygiene, secret scanning, and Semgrep passed.
- Prior frontend PR CI also passed the Web, API, security, dependency, and SBOM jobs.
- No known dependency vulnerabilities were reported in the latest dependency audit performed by
  Codex.

## Current constraints

- ADR 0003 permits a single-user, local-machine pilot only. The app must not be hosted, shared, or
  used by a second person until the documented exit requirements are met.
- The development token session is currently page-local. Protected routes need application-wide
  React memory state without browser persistence.
- No case, entity-resolution, audit, or upload screen exists yet.
- P-09 remains binding: no approval, decline, rating, score, traffic light, credit-limit
  recommendation, or binding commitment may appear in the UI.
- No backend change is currently requested by Codex.

## Next steps

1. Sync `origin/main` and create a fresh Codex worktree for the next UI slice.
2. If the OpenAPI contract changes, regenerate and commit only the declaration in a separate
   prerequisite PR; the stale-types test must pass.
3. Provide application-wide, memory-only development session context for protected routes.
4. Build the paged case list as the next screen PR, including loading, empty, error, 403, permission,
   and pagination states.
5. Build case detail, new case, edit case, entity resolution, and auditor-only audit trail as separate
   PRs in that order.
6. Add the first Playwright journey covering sign-in, case creation, information gaps, two entity
   candidates, the ambiguity stop, explicit resolution, and reason-required reopen.
7. For every UI PR, run lint, TypeScript, Vitest, production build, dependency audit, repository
   hooks, and applicable browser/E2E checks.

## Product Owner checks for the next slice

- Confirm a development token enters the protected UI without persistence.
- Confirm users without `case:read` receive a clear access-denied state.
- Confirm the case list uses only API-provided values and contains no decision-like language.
- Confirm New Case is hidden without `case:write`.
- Confirm pagination, loading, empty, error, and 403 states are understandable in plain language.
