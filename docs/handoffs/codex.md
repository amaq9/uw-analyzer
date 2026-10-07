# Codex Front-End Handoff

## Ownership

- Codex implements front-end UI work only, following the Product Owner's narrower assignment.
- Back-end, infrastructure, CI/CD, shared governance, and Claude Code's handoff remain outside Codex's ownership.
- Work uses a separate Git worktree and short-lived `codex/<topic>` branches.

## Current Status

- The Skills information-architecture slice is complete on `codex/skills-interface`.
- The interface now exposes the configured Financial Statement Assessment methodology without implying backend execution exists.
- Skill execution remains disabled until Claude Code publishes an approved versioned contract.

## Completed Work

- Built the `/web` application foundation with a responsive desktop/mobile layout.
- Added a workspace overview that communicates the controlled research sequence and human-underwriter boundary.
- Added truthful readiness and empty states without fabricated customer, case, source, or activity data.
- Added a separate enterprise sign-in screen with SSO visibly unavailable until integration is complete.
- Added component tests for the decision boundary, entity ambiguity stop-control, access/verification separation, and disabled SSO state.
- Added baseline response headers and pinned dependencies with a clean audit.
- Added a Skills destination to desktop and mobile navigation.
- Added a Financial Statement Assessment overview spotlight and detailed five-area methodology page.
- Added explicit requirements, missing-data handling, indicative-benchmark warning, and decision-boundary safeguards.
- Added tests that keep skill execution disabled while the backend contract is absent.

## Verification

- Lint, TypeScript checks, 7 component tests, and the optimized production build pass.
- npm reports zero known dependency vulnerabilities.
- Desktop and mobile browser reviews pass with no console warnings or errors; mobile navigation exposes only live destinations.
- Changes remain limited to `/web` and Codex's own handoff.

## Blockers and Risks

- OpenAPI v0.1.0 exposes health, caller identity, and audit events only; it has no skill registry or financial-assessment resource.
- The financial-assessment skill is a local Claude package, not a deployable backend capability. Its indicative benchmark reference also contains decision-like wording that must be sanitized before integration.
- The CI-owned workflow has no `/web` job yet; request frontend install, lint, typecheck, test, build, audit/license, and SBOM steps from Claude Code.
- Skill execution remains disabled. A future backend contract should preserve input periods/units, data gaps, provenance, five-area structured output, and run metadata.
- Playwright coverage starts with the first critical user workflow rather than this non-interactive information-architecture slice.
- Staging deployment and validation remain pending.

## Next Action

After Product Owner review, Claude Code should propose the versioned skill contract and sanitize benchmark wording when that later-phase work is authorized. Codex will generate client types from the approved OpenAPI contract before enabling assessment execution.
