import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.sources.schemas import AccessCategory, Health, SourceRecord

metadata = sa.MetaData()
sources = sa.Table(
    "sources",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("key", sa.Text, nullable=False),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("source_class", sa.Text, nullable=False),
    sa.Column("source_type", sa.Text, nullable=False),
    sa.Column("jurisdictions", ARRAY(sa.Text), nullable=False),
    sa.Column("access_category", sa.Text, nullable=False),
    sa.Column("auth_state", sa.Text, nullable=False),
    sa.Column("terms_notes", sa.Text),
    sa.Column("rate_limit_per_minute", sa.Integer),
    sa.Column("health", sa.Text, nullable=False),
    sa.Column("health_checked_at", sa.DateTime(timezone=True)),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("created_by", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)


class DuplicateSourceKeyError(Exception):
    pass


def _record(row: sa.RowMapping) -> SourceRecord:
    data = dict(row)
    data.pop("seq")
    return SourceRecord(**data)


class PostgresSourceStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create(self, tenant_id: str, created_by: str, fields: dict[str, Any]) -> SourceRecord:
        now = datetime.now(UTC)
        stmt = (
            sa.insert(sources)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                health="UNKNOWN",
                version=1,
                created_by=created_by,
                created_at=now,
                updated_at=now,
                **fields,
            )
            .returning(sources)
        )
        try:
            with self._engine.begin() as conn:
                return _record(conn.execute(stmt).mappings().one())
        except IntegrityError as exc:
            if "sources_tenant_id_key_key" in str(exc.orig):
                raise DuplicateSourceKeyError from None
            raise

    def get(self, source_id: uuid.UUID) -> SourceRecord | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(sa.select(sources).where(sources.c.id == source_id)).mappings().first()
            )
        return _record(row) if row else None

    def list_for_tenant(
        self,
        tenant_id: str,
        *,
        jurisdiction: str | None = None,
        access_category: AccessCategory | None = None,
    ) -> list[SourceRecord]:
        stmt = sa.select(sources).where(sources.c.tenant_id == tenant_id).order_by(sources.c.seq)
        if jurisdiction:
            # A GLOBAL source covers every jurisdiction.
            stmt = stmt.where(
                sa.or_(
                    sources.c.jurisdictions.any(jurisdiction),
                    sources.c.jurisdictions.any("GLOBAL"),
                )
            )
        if access_category:
            stmt = stmt.where(sources.c.access_category == access_category.value)
        with self._engine.connect() as conn:
            return [_record(r) for r in conn.execute(stmt).mappings().all()]

    def update(
        self, source_id: uuid.UUID, tenant_id: str, expected_version: int, changes: dict[str, Any]
    ) -> SourceRecord | None:
        """Apply changes only if the version still matches. None means it did not (conflict)."""
        now = datetime.now(UTC)
        extra: dict[str, Any] = {"health_checked_at": now} if "health" in changes else {}
        stmt = (
            sa.update(sources)
            .where(
                sources.c.id == source_id,
                sources.c.tenant_id == tenant_id,
                sources.c.version == expected_version,
            )
            .values(version=expected_version + 1, updated_at=now, **extra, **changes)
            .returning(sources)
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        return _record(row) if row else None

    def record_health(self, source_id: uuid.UUID, health: Health) -> None:
        """Health observed from a logged connector call (ADR 0009 item 6). Not a configuration
        change, so the version is not bumped. An administrator's DOWN is never overwritten, and
        DOWN is never set here: taking a source out of plans stays a person's decision."""
        if health is Health.DOWN:
            raise ValueError("Only an administrator marks a source DOWN.")
        stmt = (
            sa.update(sources)
            .where(sources.c.id == source_id, sources.c.health != Health.DOWN.value)
            .values(health=health.value, health_checked_at=datetime.now(UTC))
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)
