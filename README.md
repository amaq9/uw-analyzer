# UW Analyzer — Trade Credit Insurance Verified External Research & Evidence Agent

Decision-support platform for trade credit underwriting (Allianz / AZT). Resolves the legal
entity, researches it through controlled external sources, verifies and classifies evidence,
checks for adverse information, and hands a human underwriter a structured, auditable report.

**This system never issues an autonomous approval, decline, or credit rating.** The human
underwriter always retains decision authority (see `BRD + PRD/rulebook.md` §1, invariant P-09).

## Status

Pre-build. Phase 0 (Foundation & Governance) in progress. See `BRD + PRD/progress-log.md` for
current stage and open decisions.

## Start here

Read, in order, before writing code or changing scope:

1. `BRD + PRD/progress-log.md` — current status, next action, open decisions
2. `BRD + PRD/rulebook.md` — binding working rules and hard invariants
3. `BRD + PRD/compliance-and-documentation.md` — compliance posture, required docs
4. `BRD + PRD/security-handoff.md` — security setup checklist (OWASP ASVS 5.0.0, OWASP Top 10:2025, NIST SSDF v1.1)

Source of truth: `BRD + PRD/Trade_Credit_Research_Agent_BRD.docx` and `..._PRD.docx` (v1.0).

## Repo layout

| Path | Purpose |
|---|---|
| `/web` | Next.js + TypeScript + React UI |
| `/api` | Python + FastAPI service |
| `/worker` | Background jobs (Celery/Dramatiq + Redis) |
| `/infra` | Docker + Terraform |
| `/docs` | Architecture, ADRs, security, data dictionary, runbooks |
| `/tests/e2e` | Playwright end-to-end tests |
| `/BRD + PRD` | Source business/product requirements and governance docs |

## Setup

Not yet defined — this section will be filled in as each service is scaffolded in Phase 0.
