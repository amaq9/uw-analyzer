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

## `draft_recommendations` (migration 0006) — Restricted
A draft recommendation for the underwriter (ADR 0005, ADR 0008). Append-only: database triggers refuse
UPDATE, DELETE and TRUNCATE; a new analysis is a new version. Tenant-scoped. Outcomes, amounts and reasons
are Restricted and never copied into audit events or logs.

| Field | Meaning |
|---|---|
| `seq`, `id`, `case_id`, `tenant_id`, `version` | Order number, draft ID, case, tenant, and the case's draft version (1, 2, ...) |
| `outcome`, `band` | `APPROVE` with `FULL` or `REDUCED`, or `DECLINE` with `DECLINE` (database-checked together) |
| `requested_amount`, `requested_currency` | The case's requested exposure at drafting time |
| `recommended_amount` | Derived by the policy; never above the request (database-checked); empty for a decline |
| `ai_proposed_amount` | The analyst's own figure, kept for the agreement view |
| `rule_codes` | Which decline rules applied (for example `amount_below_floor`) |
| `content` | Summary, reasons with evidence, verified findings, factors, information gaps |
| `source`, `policy_version` | Who and what produced it (session, model, skill version) and the policy version used |
| `created_by`, `created_at` | Who and when |

Retention: TBD (legal).

## `sources` (source and connector registry, FR-2.1/2.2; migration 0007)

What the product is *capable* of reaching, per tenant. It is not evidence that a source was accessed:
only a recorded connector call can show that (FR-2.6, FR-2.7). Not case content; Internal. There is no
credential column: secrets live in a secrets store and are never saved or returned here.

| Field | Meaning |
|---|---|
| `seq`, `id`, `tenant_id`, `key` | Order number, ID, tenant, and a stable lowercase key unique within the tenant (never changes) |
| `name`, `source_type` | Display name and kind (for example `company_registry`, `court_records`, `news`) |
| `source_class` | `OFFICIAL`, `COMMERCIAL`, `SECONDARY` or `WEAK` |
| `jurisdictions` | Two-letter country codes, or `GLOBAL` (a GLOBAL source matches every jurisdiction filter) |
| `access_category` | `ACTUALLY_ACCESSIBLE`, `RESTRICTED_LICENSED`, `DISCOVERY_ONLY` or `TECHNICALLY_UNAVAILABLE` |
| `auth_state` | `NOT_REQUIRED`, `CONFIGURED` or `MISSING`; `ACTUALLY_ACCESSIBLE` with `MISSING` is refused (database-checked) |
| `terms_notes`, `rate_limit_per_minute` | Licence or terms notes; request quota |
| `health`, `health_checked_at` | `UNKNOWN`, `HEALTHY`, `DEGRADED`, `DOWN`; set by the administrator until automatic checks exist |
| `version`, `created_by`, `created_at`, `updated_at` | Optimistic concurrency and bookkeeping |

Retention: TBD (legal).

## `underwriter_decisions` (the human decision, ADR 0005 items 7 and 8; migration 0008)

The only decision in the system. Written only by a named person holding `decision:record`; append-only
(database triggers). One per draft, and only for the newest draft of a case. Restricted case content:
reasons and amounts never go into audit events or logs.

| Field | Meaning |
|---|---|
| `seq`, `id`, `case_id`, `draft_id`, `tenant_id` | Order number, ID, case, the draft decided on (unique), tenant |
| `action` | `ADOPT` (keep the draft), `CHANGE` (different outcome or amount), `REJECT` (set aside, no outcome) |
| `final_outcome`, `final_amount`, `currency` | The person's outcome and amount (empty for a reject; amount only when approving, never above the request) |
| `reason` | Written reason, required for change and reject |
| `agrees` | True only for adopt; feeds the agreement view |
| `decided_by`, `decided_at` | Who and when |

## `research_runs` and `research_steps` (research plan, FR-2.3 / FR-2.5; migration 0009)

A run is the plan and, later, the record of one research pass for a case. Steps are never created by a
model. A plan says what would be searched; it never says a source was accessed (FR-2.7). Case-linked,
Restricted.

| Field | Meaning |
|---|---|
| run `status` | `PLANNED`, `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED` (only `PLANNED` exists until the executor ships) |
| run `jurisdictions` | Countries the person named (entity, parent, operating) |
| run `versions` | App, plan rules, policy, registry versions now; prompt, model and connector versions are empty until a step uses them (P-10) |
| run `idempotency_key` | Same key on the same case returns the same run |
| step `category` | `ENTITY_REGISTRY`, `FINANCIALS`, `ADVERSE_SEARCH`, `COUNTRY_INDUSTRY` |
| step `state` | `PLANNED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `NOT_AVAILABLE`, `SKIPPED` |
| step `source_snapshot` | The registry entry as it was when planned (later registry edits do not rewrite history) |
| step `discovery_only` | Can find leads but cannot verify a material claim alone (P-06) |
| step `reason` | Why a step is not available (no source, licence not held, unavailable, down) |
| step `attempts`, `max_attempts`, `error_class` | Bounded retries (FR-2.5) |

## `connector_calls` (FR-2.6; migration 0010)

One row per executed connector attempt, written only by the executor and append-only (database triggers).
This log, not any model output, is what shows a source was accessed. Restricted (case-linked).

| Field | Meaning |
|---|---|
| `seq`, `id`, `tenant_id`, `case_id`, `run_id`, `step_id`, `source_id`, `source_key` | Order number, ID, ownership and the source reached |
| `connector_version`, `attempt` | Which connector build, and which try (unique per step) |
| `action` | Plain-language statement of what the call did |
| `access_status` | The source's access category at call time |
| `started_at`, `ended_at` | When it ran |
| `outcome` | `SUCCESS`, `ERROR` or `TIMEOUT`; `SUCCESS` requires a provenance reference (database-checked) |
| `error_class` | `retryable`, `permanent`, `timeout`, `no_provenance` |
| `provenance_ref` | Where the returned material is kept |

## `evidence`, `claims`, `claim_basis`, `claim_evidence` (Phase 3; migration 0011)

All four are append-only (database triggers). Restricted case content. There is **no verification
column**: the status is computed from the links on every read (ADR 0012).

| Table / field | Meaning |
|---|---|
| evidence `kind` | `DOCUMENT` (an upload of this case), `CONNECTOR` (a logged successful call), `WEB` (https address and read time) |
| evidence `evidence_type` | `REGISTRY`, `FINANCIAL`, `LEGAL_REGULATORY`, `NEWS`, `MACRO_INDUSTRY`, `OTHER` (sets freshness thresholds) |
| evidence `source_class`, `class_basis` | `OFFICIAL`, `COMMERCIAL`, `SECONDARY`, `WEAK`; basis `registry` (connector evidence) or `author_declared` |
| evidence `origin` | Publisher; different origins count as independent |
| evidence `is_primary`, `discovery_only` | The originating record itself; can find leads but not verify alone |
| evidence `accessed_at`, `provenance_ref`, `content_hash` | When and where it was read; hash where known |
| evidence `published_on`, `event_on` | Dates kept for freshness |
| claim `text`, `classification` | Exact proposition; `FACT`, `INTERPRETATION`, `INFERENCE`, `UNVERIFIED` |
| claim `material`, `adverse`, `credit_relevance`, `category` | Materiality and relevance |
| claim `unavailable_step_id` | A real unavailable, failed or skipped research step (for `SOURCE_UNAVAILABLE`) |
| claim_basis | The facts an interpretation or inference rests on |
| claim_evidence `relation`, `notes` | `SUPPORTS` or `CONTRADICTS`; reviewer notes |

## `escalations`, `escalation_resolutions` (Phase 4; migration 0012)

Append-only. Items that need a person. Restricted case content.

| Field | Meaning |
|---|---|
| escalation `kind` | `CONFLICT` (raised by the system, needs a claim), `MATERIAL_AMBIGUITY`, `OTHER` |
| escalation `raised_by_system`, `created_by` | System-raised conflicts show `system` |
| escalation `claim_id`, `description` | The claim at issue and a plain-language description |
| resolution `outcome` | `SUPPORTING_PREVAILS`, `CONTRADICTING_PREVAILS` (conflicts) or `NO_CLAIM_CHANGE` (others) |
| resolution `preferred_evidence_id`, `explanation` | The evidence preferred and the written reason (required) |
| resolution `resolved_by`, `resolved_at` | The named reviewer and when; one per escalation |
