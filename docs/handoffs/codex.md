# Codex Front-End Handoff

## Ownership

- Codex implements front-end UI work only, following the Product Owner's narrower assignment.
- Back-end, infrastructure, CI/CD, shared governance, and Claude Code's handoff remain outside Codex's ownership.
- Work uses a separate Git worktree and short-lived `codex/<topic>` branches.

## Current Status

- The first front-end implementation slice is complete on `codex/ui-foundation`.
- The application now has a tested Next.js/TypeScript foundation, responsive workspace shell, and enterprise access state.
- API integration is waiting on the versioned OpenAPI contract; no independent API types were introduced.

## Completed Work

- Built the `/web` application foundation with a responsive desktop/mobile layout.
- Added a workspace overview that communicates the controlled research sequence and human-underwriter boundary.
- Added truthful readiness and empty states without fabricated customer, case, source, or activity data.
- Added a separate enterprise sign-in screen with SSO visibly unavailable until integration is complete.
- Added component tests for the decision boundary, entity ambiguity stop-control, access/verification separation, and disabled SSO state.
- Added baseline response headers and pinned dependencies with a clean audit.

## Verification

- Lint, TypeScript checks, 4 component tests, and the optimized production build pass.
- npm reports zero known dependency vulnerabilities.
- Desktop and mobile browser reviews pass with no console warnings or errors.
- Changes remain limited to `/web` and Codex's own handoff.

## Blockers and Risks

- The versioned OpenAPI contract is not yet present in `docs/api/`, so authentication and live workspace data are not connected.
- The CI-owned workflow has no `/web` job yet; request frontend install, lint, typecheck, test, build, audit/license, and SBOM steps from Claude Code.
- Playwright coverage starts with the first critical user workflow rather than this non-interactive foundation.
- Staging deployment and validation remain pending.

## Next Action

After Product Owner review and publication of the OpenAPI contract, generate client types from the contract, connect the authenticated `/me` state, and begin the Phase 1 case-intake/entity-resolution UI as a separate small PR.
