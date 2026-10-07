# ADR 0001: Authentication, roles and tenant isolation

- **Status:** Accepted, 2026-10-07 (approved by the Product Owner, with the administrator change below)
- **Date:** 2026-10-07 (America/Toronto)
- **Decider:** Product Owner (approves). Author: Claude Code.

## Context
FR-0.4 requires an OIDC login skeleton, role-based access control (RBAC) and a tenant-aware
authorization layer (PRD section 5, SEC-03, SEC-04, AC-10). The identity provider (IdP) and the
tenancy model are still open decisions (PRD section 19), so the design must not depend on a vendor
and must stay tenant-aware either way. Invariant P-09 means no role or permission may exist that
approves, declines, rates or sets a credit limit.

## Decision
1. **Login:** the API accepts a bearer token (JWT) issued by an enterprise OIDC provider and checks
   it on every request: RS256 signature (keys fetched from the provider's JWKS address), issuer,
   audience, expiry, subject and a `tenant_id` claim. Anything else is rejected with a generic 401;
   the real reason is logged, never shown. MFA stays with the IdP (SEC-03).
2. **Roles to permissions:** six roles (underwriter, reviewer, research analyst, administrator,
   auditor, service) map to a fixed set of permissions in code. Roles the API does not recognise grant
   nothing. Access is deny-by-default.
3. **Tenant isolation:** every token carries one tenant. Object-level checks compare the caller's
   tenant with the object's tenant; a mismatch is denied, logged and reported as "not found" so the
   existence of another tenant's data is never confirmed.
4. **Fail-closed config:** `APP_ENV` has no default. The built-in stub IdP (for local development and
   tests) is refused unless `APP_ENV` is `local` or `test`, so it cannot run in staging or production.
5. **No decision permission (P-09):** a test fails if any permission name suggests approving,
   declining, rating, limits or binding.

Role to permission table (approved; derived from PRD section 3):

| Role | Permissions |
|---|---|
| Underwriter | case read/write, run research, annotate evidence, complete report |
| Reviewer | everything an underwriter has, plus resolve conflicts |
| Research analyst | case read, annotate evidence, run research (cannot complete a report) |
| Administrator | admin manage only (no case data; least privilege) |
| Auditor | case read, audit read |
| Service | run research only |

## Alternatives considered
- **Sessions and cookies issued by our own API:** more to build and secure; the IdP already does this.
- **Hard-wiring one vendor's SDK:** faster now, but the IdP choice is still open.
- **Database-level tenant isolation only (row-level security):** valuable defence in depth and still
  planned with the database work, but not a substitute for checks in the API layer.
- **Roles stored in our database and edited by admins:** deferred; a fixed table is easier to review
  and test for now.

## Consequences
- Switching IdP is configuration (issuer, audience, JWKS address), not a rewrite.
- Denials are logged and, since FR-0.5 (ADR 0002), written as audit events.
- The live JWKS path has only been tested with supplied keys until an IdP is chosen.
- The role table is approved. Changing it later is a small code and test change but is a
  security-model change, so it needs Product Owner approval.

## Product Owner decision (2026-10-07)
Approved with one change from the original proposal: the administrator role no longer has "case read".
Administrators manage users, roles, sources and policy; they do not need confidential case content.
If an administrator ever needs case access, assign them a second role.

## Rollback
Revert PR #11. Nothing else depends on it yet.
