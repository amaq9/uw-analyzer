# Research protocol mapping

Traces each protocol control to the code, the database rule and the test that proves it, so an
auditor can follow "the protocol says X" to "the system does X, here is the test". A control with
no entry here is not yet implemented. Updated in the same PR as the feature.

Legend: **Built** means implemented and tested. **Planned** names the phase that will build it.

## Hard invariants
| ID | Control | Code | Database rule | Test | Status |
|---|---|---|---|---|---|
| P-09 | No autonomous decision; no rating, score or traffic-light wording or UI anywhere (ADR 0004); decision wording only in a labelled draft recommendation that a named human adopts, changes or rejects (ADR 0005, not built, gated) | No decision permission or endpoint; role table; readiness is a process state with a reason, never a score | none to enforce | `test_no_permission_can_make_an_underwriting_decision`, `test_no_case_field_or_path_can_carry_a_decision`, contract path test; UI wording test (Codex, `/web`) | Built for the API (enforced on every new endpoint); UI test required per ADR 0004; ADR 0005 feature Planned (Phase 5, gated) |
| P-02 | No fabricated evidence | Missing intake inputs are reported as gaps, never filled | none | `test_a_missing_input_is_a_gap_not_a_value` | Built for intake; evidence rules Planned (Phase 3) |
| P-03 | Entity ambiguity blocks research | `app/cases/entities.py` `research_readiness` and `require_research_allowed` (the server-side gate every research start must call) | `cases.status` check; two or more open candidates set `ENTITY_AMBIGUOUS` | `test_two_candidates_make_the_case_ambiguous_and_block_research`, `test_the_server_side_gate_refuses_unresolved_cases` | Built; the gate is wired to research start in Phase 2 |
| P-07 | Ambiguity cannot be auto-closed | Only `POST .../entity-resolution` (a person with `case:write`) resolves; `status` cannot be set directly; reopening needs a reason | `entity_resolution_log` append-only triggers | `test_only_an_explicit_human_choice_resolves_it`, `test_a_case_never_resolves_by_itself`, `test_resolution_history_is_kept_and_cannot_be_edited` | Built for entity ambiguity; other escalations Planned (Phase 4) |
| P-10 | Run reproducibility | none yet | none yet | none yet | Planned (Phase 2) |
| P-01, P-04, P-05, P-06, P-08 | Source access, verification, weak sources, escalation, immutability | none yet | none yet | none yet | Planned (Phases 2 to 5) |

## Phase 1: case intake and entity resolution
| Requirement | Code | Database rule | Test | Status |
|---|---|---|---|---|
| FR-1.1 Create a case with intake fields | `app/cases/router.py` `create_case`, `schemas.py` | `cases` table, name and exposure checks | `test_cases_api.py` create tests, `test_case_schemas.py` | Built |
| FR-1.3 Missing inputs are information gaps | `schemas.py` `information_gaps` | none (computed) | `test_case_schemas.py` gap tests | Built |
| FR-1.7 Audit intake edits and entity choices | `record_event` in both routers | `audit_events` append-only triggers | `test_create_view_and_update_are_audited_without_case_content`, `test_entity_actions_are_audited_without_names_or_reasons`, `test_upload_and_download_are_audited_without_names_or_content` | Built for create, view, update, candidates, resolve, reopen, upload, rejection, download |
| AC-10 Tenant isolation | `assert_same_tenant`, tenant-filtered store | `tenant_id` on every case | `test_another_tenant_cannot_read_update_or_see_the_case`, `test_cross_tenant_attempt_is_audited_without_exposing_case_data` | Built for cases |
| Server-side validation, no mass assignment | `CaseFields` forbids unknown fields | CHECK constraints | `test_users_cannot_set_server_controlled_fields` | Built |
| FR-1.4 Entity candidates | `entity_router.py` `add_candidate` (user-entered only; connector candidates Planned, Phase 2) | `entity_candidates` | `test_candidate_lists_and_validation` | Built (user-entered) |
| FR-1.5 / AC-01 / BR-01 Ambiguity stop and explanation | `research-readiness` endpoint, `entities.py` | status check | `test_new_case_cannot_research_and_says_why`, `test_two_candidates_make_the_case_ambiguous_and_block_research`, readiness rule tests | Built |
| FR-1.2 Secure uploads (type, size, malware checks, private storage) | `app/documents/` (`validation.py`, `scanner.py`, `storage.py`, `service.py`, `router.py`) | `case_documents` append-only triggers | `test_document_validation.py`, `test_document_scanner.py`, `test_documents_api.py`, `test_documents_integration.py` (real S3 and the real ClamAV with the EICAR test file) | Built |
| FR-1.6 Aliases, former names, parent, subsidiaries | `CandidateCreate` | `entity_candidates` array columns | `test_candidate_lists_and_validation` | Built |

## Assisted mode and the draft recommendation (ADR 0005, ADR 0008)
| Requirement | Code | Database rule | Test | Status |
|---|---|---|---|---|
| Policy v1.0 applied by the server, not the author | `app/recommendation/policy.py`, `router.py` | outcome/band/amount consistency and amount never above the request | `test_recommendation_policy.py` (every band, boundary, rounding, decline rule), `test_draft_recommendations.py` | Built |
| P-02 No invented evidence | evidence schema; cited documents must be uploads of the case | none | `test_a_cited_document_must_be_a_real_upload_of_this_case`, `test_evidence_must_be_complete_and_well_formed` | Built for assisted drafts |
| P-06 / P-07 Unverified material findings do not auto-decide | unverified finding blocks the draft | none | `test_an_unverified_finding_is_not_a_decline_it_blocks_the_draft` | Built |
| P-03 Entity gate; policy 2e2 item 5 | draft needs a resolved or human-recorded unconfirmed entity | `ENTITY_UNCONFIRMED` status | `test_an_unresolved_entity_cannot_have_a_draft`, `test_entity_unconfirmed.py` | Built |
| P-08 / P-10 Immutable, versioned, reproducible drafts | version per case, source and policy version stored | append-only triggers | `test_new_drafts_get_new_versions_and_old_ones_are_kept`, `test_drafts_cannot_be_edited_or_deleted_in_the_database` | Built |
| P-09 Decision wording only in the designated places | exact allow-list | none | `tests/p09.py` used by `test_decision_wording_exists_only_in_the_designated_places` and the contract test | Built |
| Human adoption, change or rejection (ADR 0005 decisions 7 and 8) | `underwriter_decisions`, `decision:record` | append-only triggers, shape CHECKs | `tests/test_underwriter_decision.py` | Built; agreement view: `GET /api/v1/agreement`, `tests/test_agreement.py` |
| FR-2.1 / FR-2.2 Source registry; access category never implies access (P-01) | `sources` table, no credential column, accessible-needs-credential rule | CHECK constraints | `tests/test_sources_api.py` | Built (slice 1; call log FR-2.6 and plan FR-2.3 still to build) |
| FR-2.3 / FR-2.4 Research plan from case and registry; unavailable sources shown | `app/research/plan.py` (pure, deterministic), `research_runs`/`research_steps` | CHECK constraints | `tests/test_research_plan.py` | Built (planning only; execution FR-2.5/2.6 next) |
| P-03 Research blocked until entity resolved | `require_research_allowed` called on every run creation; blocked attempts audited | none | `test_run_is_blocked_until_the_entity_is_resolved` | Built |
| P-10 Every run records versions | `research_runs.versions` (app, plan rules, policy, registry; prompt/model/connectors filled by executor) | none | `test_plan_run_records_versions_steps_and_audit` | Partly built |
| FR-2.5 Background jobs: per-step state, timeout, bounded retries, backoff, resumable | `app/research/executor.py`, Postgres queue (`FOR UPDATE SKIP LOCKED`), `scripts/worker.py` | none | `tests/test_research_executor.py` | Built |
| FR-2.6 / FR-2.7 / P-01 Every connector call recorded; only an executed call shows access | `connector_calls` append-only; `accessed` derived from the log; no write API | triggers, `success_has_provenance` CHECK | `test_the_call_log_is_append_only_and_has_no_write_api`, `test_a_result_without_provenance_never_counts_as_access` | Built (no real connectors yet: steps are SKIPPED) |
| FR-3.1 to FR-3.3 Evidence, claim and many-to-many links | `evidence`, `claims`, `claim_evidence`, `claim_basis` (append-only) | triggers, shape CHECKs | `tests/test_evidence_api.py` | Built |
| FR-3.4 / P-05 Verification status computed, exactly 5 values | `app/evidence/rules.py`; no column; extra fields rejected | none | `test_status_values_are_exactly_the_five`, `test_status_cannot_be_sent_by_the_caller`, `test_everything_is_append_only_and_status_is_not_stored` | Built |
| P-04 Access and verification separate | evidence `accessed_at`/provenance vs claim `verification` | none | `test_web_evidence_keeps_access_separate_from_verification` | Built |
| P-06 / FR-3.6 Weak or discovery-only cannot verify | `rules.verify` | none | `test_weak_sources_alone_never_verify_a_material_claim`, `test_discovery_only_evidence_cannot_verify_even_if_official` | Built |
| FR-3.7 Material adverse: two independent reliable or one definitive primary | `rules.verify` (independent = distinct origin) | none | `test_material_adverse_needs_a_definitive_primary_or_two_independent_reliable` | Built (automatic attempt log in Phase 4) |
| FR-3.5 Freshness enum with dates retained | `rules.freshness`, thresholds per type | none | `test_news_freshness_boundaries` | Built |
| FR-3.8 Interpretations link their basis | `ClaimCreate` rule, `claim_basis` | none | `test_judgements_link_their_basis_and_are_not_applicable` | Built |
| P-01 / P-02 Evidence cannot invent access | connector evidence only from a logged successful call of this case | `evidence_kind_shape` CHECK | `test_connector_evidence_needs_a_logged_successful_call`, `test_a_failed_call_cannot_be_evidence` | Built |
| P-07 Material conflicts and ambiguities cannot be auto-closed | `escalations` (system-raised conflicts), reviewer-only written resolution, append-only | triggers, `conflict_has_claim` CHECK, non-empty explanation CHECK | `tests/test_escalations.py` | Built |
| Source conflict engine: both sides shown with authority/date/specificity/independence/quality; explanation required when preferring evidence | `conflict_comparison`, resolution rules | none | `test_a_reliable_contradiction_on_a_material_claim_raises_a_review_automatically`, `test_resolution_rules` | Built |
