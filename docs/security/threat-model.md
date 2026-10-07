# Threat model (initial, Phase 0)

Status: **initial draft**, reviewed at every phase. Scope: the API, worker, database and CI as they
exist or are planned. "Built" means implemented and tested today; "Planned" means not yet built.
Baselines: OWASP ASVS 5.0.0, OWASP Top 10:2025, NIST SSDF v1.1.

## Assets (what we protect)
| Asset | Why it matters |
|---|---|
| Case data, uploaded financials, evidence, reports | Confidential commercial and personal data; basis of underwriting decisions |
| Audit events | Proof of who did what; must not be alterable |
| Tenant boundary | A cross-tenant leak is a stop-ship defect |
| Underwriting decision boundary (P-09) | The system must never decide; compliance control |
| Evidence integrity (P-01, P-02, P-04 to P-08) | Fabricated or merged evidence would make reports indefensible |
| Credentials: IdP keys, connector keys, DB passwords, LLM keys | Compromise gives access to everything above |
| Source code and CI pipeline | Public repo; a poisoned pipeline poisons every release |

## Actors
Underwriters, reviewers, analysts, administrators, auditors (authenticated humans); service accounts
(workers, connectors); external attackers (anonymous or with stolen credentials); a malicious or careless
insider; a compromised dependency or CI action; hostile web content and documents read by the research
agent (prompt injection); the LLM itself (untrusted output).

## Trust boundaries
1. Internet to API (all input untrusted).
2. API to database and object storage (least-privilege credentials).
3. Worker to external sources and LLM providers (outbound; responses untrusted).
4. Retrieved web pages and uploaded documents to the LLM prompt (untrusted data, never instructions).
5. CI and the public repository to deployed artifacts (supply chain).

## Threats and mitigations
| # | Threat | Mitigation | Status |
|---|---|---|---|
| T1 | Forged, expired or wrong-audience token; `alg=none`; HS/RS key confusion | RS256-only verification, iss/aud/exp/sub required, tests for each attack | Built (PR #11) |
| T2 | Privilege escalation through roles | Fixed role-to-permission table in code, unknown roles grant nothing, deny by default | Built (PR #11) |
| T3 | Cross-tenant data access | Tenant ID from the verified token, object-level `assert_same_tenant`, 404 so existence is not revealed, denial audited | Built, and **proven on the cases endpoints** (read, list, update, audit). Must be repeated for each new data endpoint. Database row-level security is Planned |
| T4 | Stub identity provider reaching staging or production | Settings refuse `AUTH_MODE=stub` unless `APP_ENV` is local or test; no default for `APP_ENV` | Built |
| T5 | Audit trail tampering or deletion | Append-only DB triggers; exact ordering; reads audited | Built (FR-0.5). **Residual:** a DB admin can drop triggers; restricted DB role and hash chain Planned |
| T6 | Log injection or request-ID spoofing | Safe-token check on caller-supplied request IDs | Built (FR-0.5) |
| T7 | Secrets leaking into the public repo | gitleaks pre-commit and CI, GitHub push protection, `.gitignore` of local docs | Built |
| T8 | Vulnerable or malicious dependency | Lockfile enforced in CI, pip-audit, Trivy, license policy, SBOM per build | Built (FR-0.6). Dependabot alerts still off (open) |
| T9 | Poisoned CI action | Actions pinned to commit SHAs, read-only workflow permissions | Built |
| T10 | Code defects in security paths | Required review via CODEOWNERS on auth and tenant paths; semgrep SAST; strict typing | Built. Second reviewer Planned |
| T11 | LLM fabricates access or evidence (P-01, P-02) | Only an executed connector call can mark a source accessed; LLM output is schema-validated and provenance-checked before saving | Planned (Phases 2 and 3) |
| T12 | Prompt injection from retrieved pages or uploads | Retrieved content delimited and treated as data; cannot change tool policy; adversarial tests | Planned (Phase 2 onward) |
| T13 | System issues a decision or binding commitment (P-09) | No permission or endpoint for it; tests fail if one appears | Built for current surface; enforced on every new endpoint |
| T14 | Malicious upload (malware, oversized, wrong type, zip bomb, macros, scripted PDF) | Allow-list judged from file bytes, size limit (declared and while reading), ClamAV scan that fails closed, no macros, zip-bomb and PDF active-content checks, private storage, random keys, metadata append-only, download as attachment with nosniff | Built (ADR 0007). Open: encryption at rest and bucket policy (hosting), per-tenant quotas |
| T15 | Denial of service, brute force | Rate limits, connector quotas, request size limits | Planned |
| T16 | Data loss | Encrypted, tested backups; restore drills | Planned (needs hosting decision) |
| T17 | Information leakage in errors | Generic 401/403/404 messages; reasons logged and audited, never returned | Built |

## Residual risks and open items
- Hosting, identity provider and retention are undecided (PRD section 19), so transport security,
  encryption at rest, secret storage and backups cannot be finalised yet.
- No data endpoints exist yet, so tenant isolation is proven for the check, not yet for real objects.
- The live JWKS path is tested with supplied keys, not against a real identity provider.
- Release gate (PRD section 11): a cross-tenant defect, authentication bypass, fabricated source
  access or unsupported material claim is stop-ship.

## Review
Update this file in the same PR as any change to auth, tenant handling, storage, connectors or the
LLM layer. Next scheduled review: end of Phase 1.
