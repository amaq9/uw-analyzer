# Runbook: security incident

Use for: a suspected leaked secret, unauthorised access, a cross-tenant data exposure, an
authentication bypass, or a suspicious pattern in the audit log. A cross-tenant defect or an
authentication bypass is **stop-ship** and an incident by definition (PRD section 11).

Named security contact: **not yet assigned** (Product Owner to name one; open item).

## First 30 minutes
1. **Write down the time and what you saw.** Do not delete anything: logs and audit events are evidence.
2. **Contain.**
   - Leaked secret: rotate it at its source first (identity provider, database, connector or LLM key),
     then remove it from wherever it was exposed. A secret that reached the public repo is treated as
     compromised even if the commit is deleted.
   - Suspected tenant leak or bypass: stop the release or take the affected endpoint out of service.
3. **Preserve evidence.** Note the `X-Request-ID` values involved. Audit events carry them:
   `GET /audit-events` (auditor role) shows the tenant's rejected logins, permission denials and
   cross-tenant denials with timestamps and correlation IDs.
4. **Tell the Product Owner and the security contact.**

## Then
- Work out what was exposed, to whom, and for how long (audit events, repository history, CI logs).
- Fix through the normal path: a PR with tests, reviewed, scanned. No permanent bypass of branch
  protection or scans, even in an emergency.
- Legal and customer notification decisions belong to the Product Owner with legal input.
- Write a blameless post-incident review: cause, impact, fix, prevention. File it in `docs/`.

## Check it worked
The secret is rotated and the old one no longer works; the defect has a regression test that fails
without the fix; the post-incident review is written.
