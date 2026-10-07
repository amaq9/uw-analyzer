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
| Human adoption, change or rejection; agreement view (ADR 0005 decisions 7 and 8) | none yet | none yet | none yet | Next |
