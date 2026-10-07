"""Roles, permissions and the authenticated principal.

There is deliberately no permission that approves, declines, rates or sets a credit
limit (P-09): the underwriter decides outside this system.
"""

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    UNDERWRITER = "underwriter"
    REVIEWER = "reviewer"
    RESEARCH_ANALYST = "research_analyst"
    ADMINISTRATOR = "administrator"
    AUDITOR = "auditor"
    SERVICE = "service"


class Permission(StrEnum):
    CASE_READ = "case:read"
    CASE_WRITE = "case:write"
    RESEARCH_RUN = "research:run"
    EVIDENCE_ANNOTATE = "evidence:annotate"
    CONFLICT_RESOLVE = "conflict:resolve"
    REPORT_COMPLETE = "report:complete"
    ADMIN_MANAGE = "admin:manage"
    AUDIT_READ = "audit:read"


_UNDERWRITER = frozenset(
    {
        Permission.CASE_READ,
        Permission.CASE_WRITE,
        Permission.RESEARCH_RUN,
        Permission.EVIDENCE_ANNOTATE,
        Permission.REPORT_COMPLETE,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.UNDERWRITER: _UNDERWRITER,
    Role.REVIEWER: _UNDERWRITER | {Permission.CONFLICT_RESOLVE},
    Role.RESEARCH_ANALYST: frozenset(
        {Permission.CASE_READ, Permission.EVIDENCE_ANNOTATE, Permission.RESEARCH_RUN}
    ),
    Role.ADMINISTRATOR: frozenset({Permission.ADMIN_MANAGE}),  # no case data: least privilege
    Role.AUDITOR: frozenset({Permission.CASE_READ, Permission.AUDIT_READ}),
    Role.SERVICE: frozenset({Permission.RESEARCH_RUN}),
}


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    roles: frozenset[Role]

    @property
    def permissions(self) -> frozenset[Permission]:
        granted: set[Permission] = set()
        for role in self.roles:
            granted |= ROLE_PERMISSIONS[role]
        return frozenset(granted)

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions
