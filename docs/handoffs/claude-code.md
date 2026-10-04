---
Project: UW Analyzer — Trade Credit Insurance Verified External Research & Evidence Agent
Doc: Handoff — Claude Code (sanitised copy of individual task log)
---

# Handoff — Claude Code (sanitised)

This is a shortened, sanitised copy of the Claude Code session log. It tracks only work assigned to Claude Code; a separate agent works in parallel and has its own tracking. Shared governance (`rulebook.md`, BRD/PRD invariants P-01 to P-10) binds this session too.

## Project location (master copy)

- **Master copy:** `Documents\AZT Allianz - AI Project - Credit Underwriting` (the local git working copy of this repo). Confirmed by the Product Owner on 2026-10-04. All work happens here.
- **Requirements and governance docs** (BRD, PRD, Consolidated Prompt, Research Protocol, progress log, rulebook, compliance, security handoff) live in `BRD + PRD/`, which is local only and never pushed.
- Any other copy of the project folder is obsolete.

## Standing preference: how financial statements are analyzed

Use this lens whenever asked to review new financials. Lead with these five areas, not a P&L summary:

1. **Balance sheet strength:** assets, liabilities, equity buffer, asset quality (goodwill/intangibles), credit ratings.
2. **Liquidity:** current, quick and cash ratios, working capital, near-term debt maturities versus cash, undrawn facilities.
3. **Gearing:** financial debt, net debt/(net cash), lease liabilities, debt/equity, net debt/EBITDA, interest cover.
4. **Accounts receivable aging:** balance, DSO, cash absorbed by receivables, allowance for credit losses. If no aging schedule is disclosed (usual in a 10-K/10-Q), say so rather than infer it.
5. **Cash flow generation:** operating cash flow, free cash flow, FCF after dividends and buybacks, and net change in cash.

End with a short overall credit-style view (strengths, weaknesses, what to watch).

## Task log

### 2026-10-03 — Orientation and scope review
- Read the project files and the BRD and PRD (v1.0, 16 Sep 2026). Summarized scope, phases (0–7), stack and open decisions. No repo changes.

### 2026-10-03 — Financial statement reviews (SEC filings)
- **Starbucks FY2025 10-K:** reviewed with the lens above. Weak liquidity (current ratio 0.72x), shareholders' deficit, free cash flow not covering the dividend.
- **Nike Q2 FY26 10-Q:** reviewed with the lens above. Strong balance sheet (net cash, low gearing), but operating cash flow down 44% and free cash flow not covering the dividend.
- No AR aging schedule was disclosed in either filing; ratios are calculated from the filed statements.

### 2026-10-04 — Master folder consolidation
- Confirmed the master copy of the project folder (see "Project location"). The old OneDrive copy is being retired by the Product Owner.
- Moved the Consolidated Prompt and Research Protocol documents into `BRD + PRD/`, so the master holds the full set of source documents.
- Removed outdated duplicate governance docs from the repo root; the current versions are in `BRD + PRD/`.
- Added root-level handoff and governance-doc filenames to `.gitignore` so they can't be pushed by accident.

### 2026-10-04 — Two-agent working agreement
- Product Owner split the work: Codex owns the front end (`/web`, `/tests/e2e`); Claude Code owns the back end, infrastructure, CI, security tooling and the OpenAPI contract in `docs/api/`.
- Added `AGENTS.md` (shared rules for both agents) and `CLAUDE.md` (#3). Each agent works in its own git worktree on `claude/` or `codex/` branches and merges only via PR.
- Branch protection on `main` now applies to admins too, so no agent can push to `main` directly.
- Root-level full handoffs for both agents are git-ignored (#2, #5); only sanitised copies live in `docs/handoffs/`.

### 2026-10-04 — Session close
- All of today's PRs (#2–#7) merged. Both agents' workspaces in sync with `main`, no open PRs, no stray branches.
- Phase 0 setup and governance are in place; no application code yet.

## Next steps

**Product Owner:**
1. Install WSL2 (`wsl --install`, as Administrator) and restart the build machine, then confirm Docker starts. This unblocks the local Postgres and Redis environment.
2. Decide, or approve default assumptions for, the six open Phase 0 decisions: cloud provider and region, identity provider, single- vs multi-tenant, LLM provider and search tools, licensed credit-data providers, and retention/RPO/RTO/volumes.
3. Optional: enable Dependabot alerts on the repo.

**Claude Code, once the above is settled** (each as its own small PR):
1. Phase 0 CI pipeline (FR-0.6): GitHub Actions for lint, typecheck, tests, SAST, dependency and secret scanning, and SBOM, gating PRs to `main`.
2. `/api` FastAPI skeleton with a health endpoint and tests.
3. First OpenAPI contract in `docs/api/`, so Codex can start the front end against it.
4. Then FR-0.4 (auth and RBAC skeleton) and FR-0.5 (audit event service), as the decisions allow.

**Codex:** waits for Product Owner approval of its first front-end slice, then builds against the OpenAPI contract.
