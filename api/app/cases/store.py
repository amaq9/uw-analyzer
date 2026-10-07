"""Postgres storage for cases. Every query that returns a list is tenant-filtered; single-case
lookups return the tenant so the caller can enforce isolation and audit a cross-tenant attempt."""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Engine

from app.cases.schemas import CaseRecord, CaseStatus

metadata = sa.MetaData()
cases = sa.Table(
    "cases",
    metadata,
    # seq is assigned by the database: an exact creation order even when timestamps tie.
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("owner", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("legal_name", sa.Text),
    sa.Column("trading_name", sa.Text),
    sa.Column("registration_number", sa.Text),
    sa.Column("jurisdiction", sa.Text),
    sa.Column("address", sa.Text),
    sa.Column("website", sa.Text),
    sa.Column("industry", sa.Text),
    sa.Column("parent_name", sa.Text),
    sa.Column("ubo_name", sa.Text),
    sa.Column("exposure_amount", sa.Numeric(18, 2)),
    sa.Column("exposure_currency", sa.Text),
    sa.Column("terms", sa.Text),
    sa.Column("context", sa.Text),
    sa.Column("resolved_candidate_id", UUID(as_uuid=True)),
    sa.Column("resolved_by", sa.Text),
    sa.Column("resolved_at", sa.DateTime(timezone=True)),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

_FIELDS = (
    "legal_name",
    "trading_name",
    "registration_number",
    "jurisdiction",
    "address",
    "website",
    "industry",
    "parent_name",
    "ubo_name",
    "exposure_amount",
    "exposure_currency",
    "terms",
    "context",
)


def _record(row: Any) -> CaseRecord:
    data = dict(row)
    data.pop("seq")  # internal ordering key, not part of the case
    return CaseRecord(**data)


class PostgresCaseStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create(self, tenant_id: str, owner: str, fields: dict[str, Any]) -> CaseRecord:
        now = datetime.now(UTC)
        values = {name: fields.get(name) for name in _FIELDS}
        stmt = (
            sa.insert(cases)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                owner=owner,
                status=CaseStatus.DRAFT.value,
                version=1,
                created_at=now,
                updated_at=now,
                **values,
            )
            .returning(cases)
        )
        with self._engine.begin() as conn:
            return _record(conn.execute(stmt).mappings().one())

    def get(self, case_id: uuid.UUID) -> CaseRecord | None:
        with self._engine.connect() as conn:
            row = conn.execute(sa.select(cases).where(cases.c.id == case_id)).mappings().first()
        return _record(row) if row else None

    def list_for_tenant(self, tenant_id: str, limit: int, offset: int) -> list[CaseRecord]:
        stmt = (
            sa.select(cases)
            .where(cases.c.tenant_id == tenant_id)
            .order_by(cases.c.seq.desc())
            .limit(limit)
            .offset(offset)
        )
        with self._engine.connect() as conn:
            return [_record(r) for r in conn.execute(stmt).mappings().all()]

    def update(
        self,
        case_id: uuid.UUID,
        tenant_id: str,
        expected_version: int,
        changes: dict[str, Any],
    ) -> CaseRecord | None:
        """Apply changes only if the version still matches. None means it did not (conflict)."""
        stmt = (
            sa.update(cases)
            .where(
                cases.c.id == case_id,
                cases.c.tenant_id == tenant_id,
                cases.c.version == expected_version,
            )
            .values(version=expected_version + 1, updated_at=datetime.now(UTC), **changes)
            .returning(cases)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        return _record(row) if row else None
