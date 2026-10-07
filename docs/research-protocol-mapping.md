# Research protocol mapping

Traces each protocol control to the code, the database rule and the test that proves it, so an
auditor can follow "the protocol says X" to "the system does X, here is the test". A control with
no entry here is not yet implemented. Updated in the same PR as the feature.

Legend: **Built** means implemented and tested. **Planned** names the phase that will build it.

## Hard invariants
| ID | Control | Code | Database rule | Test | Status |
|---|---|---|---|---|---|
| P-09 | No autonomous decision | No decision permission or endpoint; role table | none to enforce | `test_no_permission_can_make_an_underwriting_decision`, `test_no_case_field_or_path_can_carry_a_decision`, contract path test | Built (enforced on every new endpoint) |
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
| FR-1.7 Audit intake edits and entity choices | `record_event` in both routers | `audit_events` append-only triggers | `test_create_view_and_update_are_audited_without_case_content`, `test_entity_actions_are_audited_without_names_or_reasons` | Built for create, view, update, candidates, resolve, reopen. Uploads Planned |
| AC-10 Tenant isolation | `assert_same_tenant`, tenant-filtered store | `tenant_id` on every case | `test_another_tenant_cannot_read_update_or_see_the_case`, `test_cross_tenant_attempt_is_audited_without_exposing_case_data` | Built for cases |
| Server-side validation, no mass assignment | `CaseFields` forbids unknown fields | CHECK constraints | `test_users_cannot_set_server_controlled_fields` | Built |
| FR-1.4 Entity candidates | `entity_router.py` `add_candidate` (user-entered only; connector candidates Planned, Phase 2) | `entity_candidates` | `test_candidate_lists_and_validation` | Built (user-entered) |
| FR-1.5 / AC-01 / BR-01 Ambiguity stop and explanation | `research-readiness` endpoint, `entities.py` | status check | `test_new_case_cannot_research_and_says_why`, `test_two_candidates_make_the_case_ambiguous_and_block_research`, readiness rule tests | Built |
| FR-1.2 Secure uploads | none yet | none yet | none yet | Planned (Phase 1, slice 3) |
| FR-1.6 Aliases, former names, parent, subsidiaries | `CandidateCreate` | `entity_candidates` array columns | `test_candidate_lists_and_validation` | Built |
