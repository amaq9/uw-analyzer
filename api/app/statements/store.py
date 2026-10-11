import uuid
from datetime import UTC, date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine import Engine

from app.cases.store import cases
from app.statements.schemas import AuditStatus, StatementRecord, Unit

metadata = sa.MetaData()
financial_statements = sa.Table(
    "financial_statements",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("document_id", UUID(as_uuid=True), nullable=False),
    sa.Column("period_end", sa.Date, nullable=False),
    sa.Column("currency", sa.Text, nullable=False),
    sa.Column("unit", sa.Text, nullable=False),
    sa.Column("audit_status", sa.Text, nullable=False),
    sa.Column("figures", JSONB, nullable=False),
    sa.Column("notes", sa.Text),
    sa.Column("confirmed_by", sa.Text, nullable=False),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
)


def _record(row: sa.RowMapping) -> StatementRecord:
    data = dict(row)
    data.pop("seq")
    return StatementRecord(**data)


class PostgresStatementStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_all(
        self,
        *,
        tenant_id: str,
        case_id: uuid.UUID,
        document_id: uuid.UUID,
        currency: str,
        unit: Unit,
        audit_status: AuditStatus,
        periods: list[tuple[date, dict[str, Any]]],
        notes: str | None,
        confirmed_by: str,
    ) -> list[StatementRecord]:
        now = datetime.now(UTC)
        with self._engine.begin() as conn:
            conn.execute(sa.select(cases.c.id).where(cases.c.id == case_id).with_for_update()).one()
            rows = [
                conn.execute(
                    sa.insert(financial_statements)
                    .values(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        case_id=case_id,
                        document_id=document_id,
                        period_end=end,
                        currency=currency,
                        unit=unit.value,
                        audit_status=audit_status.value,
                        figures=figures,
                        notes=notes,
                        confirmed_by=confirmed_by,
                        confirmed_at=now,
                    )
                    .returning(financial_statements)
                )
                .mappings()
                .one()
                for end, figures in periods
            ]
        return [_record(r) for r in rows]

    def latest_per_period(self, case_id: uuid.UUID, tenant_id: str) -> list[StatementRecord]:
        """The most recently confirmed set for each period end, newest period first."""
        stmt = (
            sa.select(financial_statements)
            .where(
                financial_statements.c.case_id == case_id,
                financial_statements.c.tenant_id == tenant_id,
            )
            .order_by(financial_statements.c.period_end.desc(), financial_statements.c.seq.desc())
        )
        with self._engine.connect() as conn:
            rows = [_record(r) for r in conn.execute(stmt).mappings().all()]
        latest: dict[date, StatementRecord] = {}
        for record in rows:
            latest.setdefault(record.period_end, record)
        return list(latest.values())
