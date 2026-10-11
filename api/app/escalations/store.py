import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.cases.store import cases

metadata = sa.MetaData()
escalations = sa.Table(
    "escalations",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("claim_id", UUID(as_uuid=True)),
    sa.Column("description", sa.Text, nullable=False),
    sa.Column("raised_by_system", sa.Boolean, nullable=False),
    sa.Column("created_by", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
resolutions = sa.Table(
    "escalation_resolutions",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("escalation_id", UUID(as_uuid=True), nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("outcome", sa.Text, nullable=False),
    sa.Column("preferred_evidence_id", UUID(as_uuid=True)),
    sa.Column("explanation", sa.Text, nullable=False),
    sa.Column("resolved_by", sa.Text, nullable=False),
    sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
)


class AlreadyResolvedError(Exception):
    pass


def _clean(row: sa.RowMapping) -> dict[str, Any]:
    data = dict(row)
    data.pop("seq", None)
    return data


class PostgresEscalationStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, values: dict[str, Any]) -> dict[str, Any]:
        stmt = (
            sa.insert(escalations)
            .values(id=uuid.uuid4(), created_at=datetime.now(UTC), **values)
            .returning(escalations)
        )
        with self._engine.begin() as conn:
            return _clean(conn.execute(stmt).mappings().one())

    def add_conflict_if_none_open(self, values: dict[str, Any]) -> dict[str, Any] | None:
        """Raise a conflict escalation for a claim unless one is already open. Locks the case so
        two requests cannot both raise it."""
        with self._engine.begin() as conn:
            conn.execute(
                sa.select(cases.c.id).where(cases.c.id == values["case_id"]).with_for_update()
            ).one()
            open_count = conn.execute(
                sa.select(sa.func.count())
                .select_from(escalations)
                .outerjoin(resolutions, resolutions.c.escalation_id == escalations.c.id)
                .where(
                    escalations.c.claim_id == values["claim_id"],
                    escalations.c.kind == "CONFLICT",
                    resolutions.c.id.is_(None),
                )
            ).scalar_one()
            if open_count:
                return None
            row = (
                conn.execute(
                    sa.insert(escalations)
                    .values(id=uuid.uuid4(), created_at=datetime.now(UTC), **values)
                    .returning(escalations)
                )
                .mappings()
                .one()
            )
            return _clean(row)

    def get(self, escalation_id: uuid.UUID) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(sa.select(escalations).where(escalations.c.id == escalation_id))
                .mappings()
                .first()
            )
        return _clean(row) if row else None

    def list_for_case(self, case_id: uuid.UUID, tenant_id: str) -> list[dict[str, Any]]:
        stmt = (
            sa.select(escalations)
            .where(escalations.c.case_id == case_id, escalations.c.tenant_id == tenant_id)
            .order_by(escalations.c.seq)
        )
        with self._engine.connect() as conn:
            return [_clean(r) for r in conn.execute(stmt).mappings().all()]

    def resolution_of(self, escalation_id: uuid.UUID) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(
                    sa.select(resolutions).where(resolutions.c.escalation_id == escalation_id)
                )
                .mappings()
                .first()
            )
        return _clean(row) if row else None

    def resolve(self, values: dict[str, Any]) -> dict[str, Any]:
        stmt = (
            sa.insert(resolutions)
            .values(id=uuid.uuid4(), resolved_at=datetime.now(UTC), **values)
            .returning(resolutions)
        )
        try:
            with self._engine.begin() as conn:
                return _clean(conn.execute(stmt).mappings().one())
        except IntegrityError as exc:
            if "escalation_resolutions_escalation_id_key" in str(exc.orig):
                raise AlreadyResolvedError from None
            raise

    def latest_conflict_resolution(self, claim_id: uuid.UUID) -> dict[str, Any] | None:
        stmt = (
            sa.select(resolutions)
            .join(escalations, escalations.c.id == resolutions.c.escalation_id)
            .where(escalations.c.claim_id == claim_id, escalations.c.kind == "CONFLICT")
            .order_by(resolutions.c.seq.desc())
            .limit(1)
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _clean(row) if row else None
