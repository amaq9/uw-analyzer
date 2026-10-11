# ADR 0012: Evidence, claims and computed verification (Phase 3)

- **Status:** Accepted, 2026-10-11 (Product Owner delegated Phases 2 to 5 to Claude Code; ADR 0003)
- **Date:** 2026-10-11 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Decision
1. **Four append-only tables** (migration 0011): `evidence`, `claims`, `claim_basis`, `claim_evidence`.
   Mistakes are corrected by adding, never editing (P-08 spirit, audit).
2. **Verification status is computed, never stored or accepted** (FR-3.4, P-05). It is one of exactly five
   values and is derived on every read by `app/evidence/rules.py` (versioned `RULES_VERSION`). There is
   no column for it and no field a caller can send; unknown fields are rejected. A model or UI cannot set it.
3. **Access and verification are separate** (P-04). Evidence carries `accessed_at`, kind, provenance and the
   connector-call link; the claim carries the computed verification. The API never merges them.
4. **Connector evidence must come from a logged successful call of this case** (P-01, FR-2.7). The server
   derives source, class, provenance, access time and the discovery flag from the call log; the author
   cannot set them. Documents must be real uploads of the case. Web evidence needs an https address and
   the time it was read.
5. **Honest limits on classification.** For document and web evidence the author declares the source
   class (official, commercial, secondary, weak). The API labels this `author_declared` so reports can
   show it; connector evidence is labelled `registry`.
6. **Rules** (see the module docstring): reliable = official or commercial and not discovery-only;
   weak or discovery-only evidence never verifies a material claim (P-06, FR-3.6); a material adverse
   claim needs a definitive primary source or two independent reliable sources, where independent means
   different `origin` (FR-3.7); a reliable contradiction blocks `VERIFIED` and is flagged as a conflict
   for a person to resolve (P-07; the resolution workflow arrives with the conflict engine in Phase 4);
   interpretations and inferences are `NOT_APPLICABLE` and must link the facts they rest on if material
   (FR-3.8); `SOURCE_UNAVAILABLE` requires pointing at a real unavailable, failed or skipped research step.
7. **Freshness** (CURRENT, RECENT, STALE, HISTORICAL) is computed from the event, publication or access
   date with thresholds per evidence type (FR-3.5); the dates are always kept.
8. **Permissions, no change to ADR 0001:** write needs `research:run`, read needs `case:read`. Audit has
   ids only.

## Limits and next
- The two-source corroboration *attempt* (FR-3.7) is recorded by what is linked; an automatic attempt
  log arrives with the adverse-search module (Phase 4).
- A claim's text is fixed. Wrong claims are superseded by new ones; a supersede link is a Phase 5 concern.
