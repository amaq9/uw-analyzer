# Data dictionary

Every table, its fields, sensitivity class (see `security/data-classification.md`) and retention.
Retention periods are an open decision (PRD section 19), shown as "TBD (legal)". Update this file in
the same PR as any schema change.

## `audit_events` (migration 0001) — Confidential
Append-only: database triggers refuse UPDATE, DELETE and TRUNCATE (ADR 0002).

| Field | Meaning |
|---|---|
| `seq` | Database-assigned order number (exact ordering) |
| `id` | Event ID |
| `occurred_at` | When it happened (UTC) |
| `tenant_id` | Caller's tenant; empty for requests with no valid sign-in |
| `actor` | Who (the sign-in subject); empty if unknown |
| `action` | `auth.rejected`, `authz.denied`, `authz.cross_tenant_denied`, `audit.read`, `case.created`, `case.viewed`, `case.updated` |
| `outcome` | `success`, `denied` or `failure` |
| `resource_type`, `resource_id` | What was acted on (for cases: `case` and the case ID) |
| `correlation_id` | The request's `X-Request-ID` |
| `details` | Short codes only (permission name, changed field names, version). **Never case content** |

Retention: TBD (legal).

## `cases` (migration 0002) — Restricted
One row per underwriting case. Always filtered by `tenant_id`; the API denies and audits cross-tenant
access (AC-10).

| Field | Meaning |
|---|---|
| `seq` | Database-assigned creation order (exact ordering; not returned by the API) |
| `id` | Case ID |
| `tenant_id` | Owning tenant (never returned by the API) |
| `owner` | Sign-in subject of the creator |
| `status` | `DRAFT`, `ENTITY_AMBIGUOUS` or `ENTITY_RESOLVED` (database-checked). Later phases add research and review statuses |
| `legal_name`, `trading_name` | At least one is required (database-checked) |
| `registration_number`, `jurisdiction`, `address`, `website`, `industry` | Optional intake fields |
| `parent_name`, `ubo_name` | Parent company and ultimate beneficial owner (optional) |
| `exposure_amount`, `exposure_currency` | Requested exposure, exact decimal (18,2, not negative) and a 3-letter code; both or neither (database-checked) |
| `terms`, `context` | Requested payment terms and free-text context |
| `version` | Starts at 1, +1 on each update; used to refuse stale edits (409) |
| `created_at`, `updated_at` | UTC timestamps |

**Information gaps are computed, not stored:** a missing material input (legal name, registration
number, jurisdiction, address, industry, website, exposure, terms, or ownership) is reported on every
read as a gap. The system never fills a missing value (FR-1.3, P-02). Stored gap records with a
resolution state arrive with the research phases.

Retention: TBD (legal). Deletion and export policy: TBD (legal).
