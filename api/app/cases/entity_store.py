"""Storage for entity candidates and resolution. Each action locks the case row inside a single
transaction, so concurrent actions cannot leave the status inconsistent with the candidates."""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.engine import Connection, Engine

from app.cases.entities import CandidateOut
from app.cases.schemas import CaseStatus
from app.cases.store import cases

metadata = sa.MetaData()
candidates = sa.Table(
    "entity_candidates",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("state", sa.Text, nullable=False),
    sa.Column("source", sa.Text, nullable=False),
    sa.Column("legal_name", sa.Text, nullable=False),
    sa.Column("registration_number", sa.Text),
    sa.Column("jurisdiction", sa.Text),
    sa.Column("address", sa.Text),
    sa.Column("website", sa.Text),
    sa.Column("parent_name", sa.Text),
    sa.Column("aliases", ARRAY(sa.Text), nullable=False),
    sa.Column("former_names", ARRAY(sa.Text), nullable=False),
    sa.Column("subsidiaries", ARRAY(sa.Text), nullable=False),
    sa.Column("created_by", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
resolution_log = sa.Table(
    "entity_resolution_log",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("action", sa.Text, nullable=False),
    sa.Column("candidate_id", UUID(as_uuid=True)),
    sa.Column("actor", sa.Text, nullable=False),
    sa.Column("note", sa.Text),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
)


class EntityConflictError(Exception):
    """The action is not allowed in the case's current state. The message is safe to show."""


class CaseMissingError(Exception):
    pass


class CandidateMissingError(Exception):
    pass


def _candidate(row: Any) -> CandidateOut:
    data = dict(row)
    data.pop("seq")
    data.pop("tenant_id")
    return CandidateOut(**data)


def _lock_case(conn: Connection, case_id: uuid.UUID, tenant_id: str) -> CaseStatus:
    status = conn.execute(
        sa.select(cases.c.status)
        .where(cases.c.id == case_id, cases.c.tenant_id == tenant_id)
        .with_for_update()
    ).scalar_one_or_none()
    if status is None:
        raise CaseMissingError
    return CaseStatus(status)


def _open_count(conn: Connection, case_id: uuid.UUID) -> int:
    return int(
        conn.execute(
            sa.select(sa.func.count())
            .select_from(candidates)
            .where(candidates.c.case_id == case_id, candidates.c.state == "candidate")
        ).scalar_one()
    )


def _status_for(open_candidates: int) -> CaseStatus:
    return CaseStatus.ENTITY_AMBIGUOUS if open_candidates >= 2 else CaseStatus.DRAFT


class PostgresEntityStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def open_candidate_count(self, case_id: uuid.UUID) -> int:
        with self._engine.connect() as conn:
            return _open_count(conn, case_id)

    def list_candidates(self, case_id: uuid.UUID, tenant_id: str) -> list[CandidateOut]:
        stmt = (
            sa.select(candidates)
            .where(candidates.c.case_id == case_id, candidates.c.tenant_id == tenant_id)
            .order_by(candidates.c.seq)
        )
        with self._engine.connect() as conn:
            return [_candidate(r) for r in conn.execute(stmt).mappings().all()]

    def add_candidate(
        self, case_id: uuid.UUID, tenant_id: str, actor: str, fields: dict[str, Any]
    ) -> tuple[CandidateOut, CaseStatus]:
        with self._engine.begin() as conn:
            if _lock_case(conn, case_id, tenant_id) is CaseStatus.ENTITY_RESOLVED:
                raise EntityConflictError(
                    "The legal entity has already been chosen. Reopen the resolution to add "
                    "another candidate."
                )
            row = (
                conn.execute(
                    sa.insert(candidates)
                    .values(
                        id=uuid.uuid4(),
                        case_id=case_id,
                        tenant_id=tenant_id,
                        state="candidate",
                        source="user_entered",
                        created_by=actor,
                        created_at=datetime.now(UTC),
                        **fields,
                    )
                    .returning(candidates)
                )
                .mappings()
                .one()
            )
            new_status = _status_for(_open_count(conn, case_id))
            conn.execute(
                sa.update(cases).where(cases.c.id == case_id).values(status=new_status.value)
            )
        return _candidate(row), new_status

    def resolve(
        self,
        case_id: uuid.UUID,
        tenant_id: str,
        actor: str,
        candidate_id: uuid.UUID,
        note: str | None,
    ) -> None:
        now = datetime.now(UTC)
        with self._engine.begin() as conn:
            if _lock_case(conn, case_id, tenant_id) is CaseStatus.ENTITY_RESOLVED:
                raise EntityConflictError("The legal entity has already been chosen.")
            chosen = conn.execute(
                sa.select(candidates.c.id).where(
                    candidates.c.id == candidate_id,
                    candidates.c.case_id == case_id,
                    candidates.c.tenant_id == tenant_id,
                    candidates.c.state == "candidate",
                )
            ).scalar_one_or_none()
            if chosen is None:
                raise CandidateMissingError
            conn.execute(
                sa.update(candidates)
                .where(candidates.c.case_id == case_id, candidates.c.state == "candidate")
                .values(
                    state=sa.case((candidates.c.id == candidate_id, "selected"), else_="rejected")
                )
            )
            conn.execute(
                sa.update(cases)
                .where(cases.c.id == case_id)
                .values(
                    status=CaseStatus.ENTITY_RESOLVED.value,
                    resolved_candidate_id=candidate_id,
                    resolved_by=actor,
                    resolved_at=now,
                )
            )
            conn.execute(
                sa.insert(resolution_log).values(
                    id=uuid.uuid4(),
                    case_id=case_id,
                    tenant_id=tenant_id,
                    action="resolved",
                    candidate_id=candidate_id,
                    actor=actor,
                    note=note,
                    occurred_at=now,
                )
            )

    def reopen(self, case_id: uuid.UUID, tenant_id: str, actor: str, reason: str) -> CaseStatus:
        now = datetime.now(UTC)
        with self._engine.begin() as conn:
            if _lock_case(conn, case_id, tenant_id) is not CaseStatus.ENTITY_RESOLVED:
                raise EntityConflictError(
                    "The legal entity has not been chosen, so there is nothing to reopen."
                )
            conn.execute(
                sa.update(candidates)
                .where(candidates.c.case_id == case_id)
                .values(state="candidate")
            )
            new_status = _status_for(_open_count(conn, case_id))
            conn.execute(
                sa.update(cases)
                .where(cases.c.id == case_id)
                .values(
                    status=new_status.value,
                    resolved_candidate_id=None,
                    resolved_by=None,
                    resolved_at=None,
                )
            )
            conn.execute(
                sa.insert(resolution_log).values(
                    id=uuid.uuid4(),
                    case_id=case_id,
                    tenant_id=tenant_id,
                    action="reopened",
                    candidate_id=None,
                    actor=actor,
                    note=reason,
                    occurred_at=now,
                )
            )
        return new_status

    def log_for_case(self, case_id: uuid.UUID, tenant_id: str) -> list[dict[str, Any]]:
        stmt = (
            sa.select(resolution_log)
            .where(resolution_log.c.case_id == case_id, resolution_log.c.tenant_id == tenant_id)
            .order_by(resolution_log.c.seq)
        )
        with self._engine.connect() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]
