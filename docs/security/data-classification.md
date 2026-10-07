# Data classification (initial, Phase 0)

Every stored entity gets a class. The class decides who may see it, how it is stored, whether it may
appear in logs, and how long it is kept. **Retention periods are an open decision** (PRD section 19);
the column below says what must be decided, not a number.

| Class | Meaning | Examples | Handling |
|---|---|---|---|
| **Restricted** | Customer case content and anything that could identify or harm a person or tenant | Uploaded financial statements and credit reports; case fields (names, registration numbers, addresses, exposure, terms); evidence excerpts and snapshots; reports; ultimate-owner (UBO) and individual data | Encrypted at rest and in transit; tenant-scoped; never in logs, prompts to non-approved providers, error messages or the repo; access audited; retention and deletion per legal decision |
| **Confidential** | Internal operational data | Audit events; research run records (prompt, model, connector, policy, app versions); connector configuration (without secrets); user and role assignments | Tenant-scoped where it has a tenant; audit events append-only; no secrets inside |
| **Secret** | Credentials | IdP client secrets, connector and LLM API keys, database passwords, signing keys | Managed secret store only; never in Git, logs, prompts, client bundles or tickets; rotated |
| **Internal** | Non-sensitive project material | ADRs, runbooks, API contract, threat model (sanitised) | Lives in the repo; no real customer or personal data |
| **Public** | Safe to publish | Source code, tests with synthetic data | Public repo; synthetic data only |

## Rules that follow
- Real customer or entity data never goes in the repo, tests, fixtures or examples. Test data is
  synthetic.
- Audit event `details` hold short codes (for example the permission name), never case content.
- Log lines carry identifiers (subject, tenant, correlation ID), never case content or tokens.
- Licensed data (D&B, Coface and similar) keeps its provider, report date and contractual limits on
  retention and display with the record (FR-7.2).
- Each new table gets a class in `docs/data-dictionary.md` in the same PR that creates it.

## Current tables
| Table | Class | Notes |
|---|---|---|
| `audit_events` | Confidential | Append-only. `details` must stay free of Restricted content. `tenant_id` null for unauthenticated events. Retention undecided |
