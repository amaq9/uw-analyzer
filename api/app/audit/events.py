"""Audit event model and storage backends.

Audit events are kept separate from diagnostic logs (SEC-10). The Postgres table is
append-only at the database level (see the migration): UPDATE, DELETE and TRUNCATE raise.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine import Engine


class Outcome(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"


class Action(StrEnum):
    AUTH_REJECTED = "auth.rejected"
    AUTHZ_DENIED = "authz.denied"
    CROSS_TENANT_DENIED = "authz.cross_tenant_denied"
    AUDIT_READ = "audit.read"
    CASE_CREATED = "case.created"
    CASE_VIEWED = "case.viewed"
    CASE_UPDATED = "case.updated"
    ENTITY_CANDIDATE_ADDED = "entity.candidate_added"
    ENTITY_RESOLVED = "entity.resolved"
    ENTITY_REOPENED = "entity.reopened"
    ENTITY_UNCONFIRMED = "entity.unconfirmed"
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_REJECTED = "document.rejected"
    DOCUMENT_DOWNLOADED = "document.downloaded"


@dataclass(frozen=True)
class AuditEvent:
    action: Action | str
    outcome: Outcome
    correlation_id: str
    tenant_id: str | None = None
    actor: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> None: ...

    def list_for_tenant(self, tenant_id: str, limit: int) -> list[AuditEvent]: ...


class InMemoryAuditSink:
    """For unit tests. Not used outside tests."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)

    def list_for_tenant(self, tenant_id: str, limit: int) -> list[AuditEvent]:
        mine = [e for e in self.events if e.tenant_id == tenant_id]
        return list(reversed(mine))[:limit]  # insertion order is exact; timestamps may tie


metadata = sa.MetaData()
audit_events = sa.Table(
    "audit_events",
    metadata,
    # seq is assigned by the database and gives an exact order even when timestamps tie.
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("tenant_id", sa.Text),
    sa.Column("actor", sa.Text),
    sa.Column("action", sa.Text, nullable=False),
    sa.Column("outcome", sa.Text, nullable=False),
    sa.Column("resource_type", sa.Text),
    sa.Column("resource_id", sa.Text),
    sa.Column("correlation_id", sa.Text, nullable=False),
    sa.Column("details", JSONB, nullable=False),
)


class PostgresAuditSink:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def record(self, event: AuditEvent) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                sa.insert(audit_events).values(
                    id=event.id,
                    occurred_at=event.occurred_at,
                    tenant_id=event.tenant_id,
                    actor=event.actor,
                    action=str(event.action),
                    outcome=event.outcome.value,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    correlation_id=event.correlation_id,
                    details=event.details,
                )
            )

    def list_for_tenant(self, tenant_id: str, limit: int) -> list[AuditEvent]:
        query = (
            sa.select(audit_events)
            .where(audit_events.c.tenant_id == tenant_id)
            .order_by(audit_events.c.seq.desc())
            .limit(limit)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [
            AuditEvent(
                id=r["id"],
                occurred_at=r["occurred_at"],
                tenant_id=r["tenant_id"],
                actor=r["actor"],
                action=r["action"],
                outcome=Outcome(r["outcome"]),
                resource_type=r["resource_type"],
                resource_id=r["resource_id"],
                correlation_id=r["correlation_id"],
                details=r["details"],
            )
            for r in rows
        ]
