# ADR 0014: Research reports, completion gates and immutable versions (Phase 5)

- **Status:** Accepted, 2026-10-11. Wording "evidence confidence" (High, Moderate, Low) confirmed by the Product Owner on 2026-10-11.
- **Date:** 2026-10-11 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.

## Decision
1. **Preview is free, completion is gated.** `GET /cases/{id}/report-preview` shows the report as it
   would be written now and every completion gate. `POST /cases/{id}/reports` (`report:complete`)
   re-checks the gates on the server and stores an immutable version (P-08). A blocked attempt is audited.
2. **Gates:** the entity is resolved (P-03); no open escalation (P-07); no research run queued or running;
   something has been recorded; every material claim is linked to evidence or marked unavailable (no
   unsupported material claim completes).
3. **Immutable and tamper-evident.** `report_versions` is append-only (database triggers); each version
   stores the content snapshot, its SHA-256, and the versions used (app, evidence rules, confidence
   rules, connectors, run ids; P-10). Reads recompute the hash and report `integrity_verified`.
   Amendments are new versions; the history is listed newest first.
4. **Content, all derived from the case's own records:** verification log (sources reviewed by category
   from the latest finished run, with `accessed` only if a connector call succeeded, plus unavailable
   ones with reasons), material findings and unverified claims with "show evidence" ids, conflicts and
   their resolutions, information gaps, limitations (payment behaviour not assessed), adverse-search
   statement, counts and the required final statement with an as-of time.
5. **Counts never blur access.** Connector sources accessed, documents reviewed and web sources recorded
   by an analyst are separate numbers.
6. **Negative-search wording is a fixed template** that appears only if a relevant source was really
   searched, always with what was not searched and "This does not mean that none exists." Otherwise it
   says the adverse search was not performed.
7. **Evidence confidence (HIGH, MODERATE, LOW), provisional wording, deterministic rules, versioned:**
   LOW if nothing was accessed, no material factual claim exists, anything awaits review, or a material
   adverse claim is not verified; HIGH if every material factual claim is verified on current or recent
   evidence and nothing awaits review; otherwise MODERATE. Each level comes with plain-language
   explanations. It is about how well the evidence supports the findings, never a score, rating or colour
   (ADR 0004 point 6). The Product Owner confirms the wording; changing it is a copy change.
8. **No decision content.** A report has no recommendation, outcome or amount. The draft recommendation
   (ADR 0005) is separate and unchanged. The P-09 contract test covers the new schemas.
