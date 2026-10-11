# ADR 0015: The project's skills are the main analyzer; first public-registry connectors

- **Status:** Accepted, 2026-10-11 (Product Owner decision: no Anthropic API key; use the skills as the main analyzer)
- **Date:** 2026-10-11 (America/Toronto)
- **Decider:** Product Owner. Author: Claude Code.
- **Amends:** ADR 0006 (the API adapter is not built); makes ADR 0008 (assisted mode) the primary way
  the analysis is produced, not a stopgap.

## Decision
1. **No API key and no AI-provider adapter.** The analysis is done by a Claude Code session using the
   project's skills (financial statement assessment and the policy), working through the same checked
   API as everyone else. The server still validates everything: the analyst cannot set verification
   status, cannot mark a source accessed, cannot choose the recommendation outcome or amount, and cannot
   record a decision, resolve a review item or complete a report. Those stay with the rules and named people.
2. **Division of labour.** Connectors (code, no AI) fetch public material and keep exact snapshots with
   hashes. The analyst session reads the snapshots and uploaded documents, applies the skills, and submits
   evidence, claims and a draft recommendation. A person decides.
3. **First real connectors, free public registries only, no keys:**
   - `sec-edgar`: U.S. SEC filer index, filing list and XBRL company facts (official; financial filings).
   - `gleif`: Global LEI register: legal entity identity and ownership links (official; company registry).
   Each reaches one registry over https on a fixed host allow-list, with no redirects, a 30 MB cap, a
   timeout, and a contact address in the User-Agent (`CONNECTOR_CONTACT`, set by the Product Owner).
4. **Never guess an entity.** SEC lookup needs an exact normalised name match to exactly one filer, or a
   CIK in the registration number; otherwise the call ends `permanent:no_unique_match` and nothing is
   saved. An empty answer from a registry is a real, logged negative result.
5. **Snapshots** (`snapshots/<tenant>/<case>/<random>` in private storage) hold the exact bytes received;
   the provenance reference carries the SHA-256. `GET /cases/{id}/snapshots?ref=` returns them after
   checking tenant, case and hash, and is audited. Connector evidence points at the call that fetched it.
6. **Data caution.** Searching sends the company name to the registry. Document text is not sent anywhere:
   with no API provider, uploaded documents and policy text stay on this computer and in this session.
7. **Not yet covered** (no free keyless official source chosen): adverse media and court records, sector
   outlook, sanctions lists, non-U.S. financial filings. These categories stay `NOT_AVAILABLE` in the plan
   and the report says so. Candidates: OFAC SDN list, World Bank and FRED macro data, GDELT news, CourtListener.
