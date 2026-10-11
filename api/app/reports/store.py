import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine import Engine

from app.cases.store import cases
from app.reports.schemas import ReportRecord

metadata = sa.MetaData()
report_versions = sa.Table(
    "report_versions",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("note", sa.Text),
    sa.Column("content", JSONB, nullable=False),
    sa.Column("content_hash", sa.Text, nullable=False),
    sa.Column("versions", JSONB, nullable=False),
    sa.Column("created_by", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


def hash_content(content: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON, so any later change to the stored text is detectable."""
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record(row: sa.RowMapping) -> ReportRecord:
    data = dict(row)
    data.pop("seq")
    return ReportRecord(**data)


class PostgresReportStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(
        self,
        *,
        case_id: uuid.UUID,
        tenant_id: str,
        note: str | None,
        content: dict[str, Any],
        versions: dict[str, Any],
        created_by: str,
    ) -> ReportRecord:
        with self._engine.begin() as conn:
            # Lock the case so two completions cannot receive the same version number.
            conn.execute(sa.select(cases.c.id).where(cases.c.id == case_id).with_for_update()).one()
            version = (
                conn.execute(
                    sa.select(sa.func.coalesce(sa.func.max(report_versions.c.version), 0)).where(
                        report_versions.c.case_id == case_id
                    )
                ).scalar_one()
                + 1
            )
            row = (
                conn.execute(
                    sa.insert(report_versions)
                    .values(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        case_id=case_id,
                        version=version,
                        note=note,
                        content=content,
                        content_hash=hash_content(content),
                        versions=versions,
                        created_by=created_by,
                        created_at=datetime.now(UTC),
                    )
                    .returning(report_versions)
                )
                .mappings()
                .one()
            )
        return _record(row)

    def list_for_case(self, case_id: uuid.UUID, tenant_id: str) -> list[ReportRecord]:
        stmt = (
            sa.select(report_versions)
            .where(report_versions.c.case_id == case_id, report_versions.c.tenant_id == tenant_id)
            .order_by(report_versions.c.version.desc())
        )
        with self._engine.connect() as conn:
            return [_record(r) for r in conn.execute(stmt).mappings().all()]

    def get(self, case_id: uuid.UUID, version: int) -> ReportRecord | None:
        stmt = sa.select(report_versions).where(
            report_versions.c.case_id == case_id, report_versions.c.version == version
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _record(row) if row else None
