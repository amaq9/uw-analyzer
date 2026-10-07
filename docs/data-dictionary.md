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

Also holds `resolved_candidate_id`, `resolved_by`, `resolved_at` (set when a person chooses the
legal entity; cleared on reopen).

**Information gaps are computed, not stored:** a missing material input (legal name, registration
number, jurisdiction, address, industry, website, exposure, terms, or ownership) is reported on every
read as a gap. The system never fills a missing value (FR-1.3, P-02). Stored gap records with a
resolution state arrive with the research phases.

Retention: TBD (legal). Deletion and export policy: TBD (legal).

## `entity_candidates` (migration 0003) — Restricted
Plausible legal entities for a case. Always entered by a person (`source` is `user_entered`; later
phases add connector sources). Tenant-scoped.

| Field | Meaning |
|---|---|
| `seq`, `id`, `case_id`, `tenant_id` | Order number, candidate ID, owning case and tenant |
| `state` | `candidate`, `selected` or `rejected` (database-checked) |
| `legal_name` | Required |
| `registration_number`, `jurisdiction`, `address`, `website`, `parent_name` | Optional |
| `aliases`, `former_names`, `subsidiaries` | Lists kept for later search templates (FR-1.6) |
| `created_by`, `created_at` | Who entered it and when |

Retention: TBD (legal).

## `entity_resolution_log` (migration 0003) — Restricted
The permanent record of who chose or reopened a case's legal entity, and why. Append-only: database
triggers refuse UPDATE, DELETE and TRUNCATE (P-07). The free-text `note` is Restricted and is never
copied into `audit_events`.

| Field | Meaning |
|---|---|
| `seq`, `id`, `case_id`, `tenant_id` | Order number, entry ID, case and tenant |
| `action` | `resolved` or `reopened` |
| `candidate_id` | The chosen candidate (for `resolved`) |
| `actor`, `occurred_at` | Who and when |
| `note` | The person's reason or note |

Retention: TBD (legal).

## `case_documents` (migration 0004) — Restricted
Metadata for uploaded files (the files themselves are in private object storage under random keys).
Append-only: database triggers refuse UPDATE, DELETE and TRUNCATE. Tenant-scoped. The file name and contents
are Restricted and never copied into audit events or logs.

| Field | Meaning |
|---|---|
| `seq`, `id`, `case_id`, `tenant_id` | Order number, document ID, owning case and tenant |
| `category` | `financial_statement`, `credit_report` or `supporting` (database-checked) |
| `original_filename` | Cleaned display name (no path or control characters, at most 150 characters) |
| `content_type` | Type detected from the file's contents (not what the browser claimed) |
| `size_bytes`, `sha256` | Exact size and SHA-256 of the stored bytes |
| `storage_key` | Random key in object storage (`tenant/random/random`); never returned by the API |
| `scan_status`, `scanned_at` | Always `clean` (an infected file is never recorded) and when it was scanned |
| `uploaded_by`, `uploaded_at` | Who and when |

Retention and controlled deletion: TBD (legal).
