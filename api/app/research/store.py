import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.engine import Engine

from app.cases.store import cases
from app.research.plan import PlannedStep
from app.research.schemas import RunRecord, StepRecord

metadata = sa.MetaData()
research_runs = sa.Table(
    "research_runs",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("trigger", sa.Text, nullable=False),
    sa.Column("jurisdictions", ARRAY(sa.Text), nullable=False),
    sa.Column("versions", JSONB, nullable=False),
    sa.Column("idempotency_key", sa.Text),
    sa.Column("correlation_id", sa.Text, nullable=False),
    sa.Column("created_by", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("completed_at", sa.DateTime(timezone=True)),
)
research_steps = sa.Table(
    "research_steps",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("run_id", UUID(as_uuid=True), nullable=False),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("ordinal", sa.Integer, nullable=False),
    sa.Column("category", sa.Text, nullable=False),
    sa.Column("source_id", UUID(as_uuid=True)),
    sa.Column("source_snapshot", JSONB, nullable=False),
    sa.Column("discovery_only", sa.Boolean, nullable=False),
    sa.Column("state", sa.Text, nullable=False),
    sa.Column("reason", sa.Text),
    sa.Column("attempts", sa.Integer, nullable=False),
    sa.Column("max_attempts", sa.Integer, nullable=False),
    sa.Column("error_class", sa.Text),
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("finished_at", sa.DateTime(timezone=True)),
)


def _run(row: sa.RowMapping) -> RunRecord:
    data = dict(row)
    data.pop("seq")
    return RunRecord(**data)


def _step(row: sa.RowMapping) -> StepRecord:
    data = dict(row)
    for dropped in ("seq", "case_id", "tenant_id"):
        data.pop(dropped)
    return StepRecord(**data)


class PostgresResearchStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_by_idempotency_key(self, case_id: uuid.UUID, key: str) -> RunRecord | None:
        stmt = sa.select(research_runs).where(
            research_runs.c.case_id == case_id, research_runs.c.idempotency_key == key
        )
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _run(row) if row else None

    def create_run(
        self,
        *,
        case_id: uuid.UUID,
        tenant_id: str,
        jurisdictions: list[str],
        versions: dict[str, Any],
        idempotency_key: str | None,
        correlation_id: str,
        created_by: str,
        steps: list[PlannedStep],
        max_attempts: int = 3,
    ) -> RunRecord:
        run_id = uuid.uuid4()
        with self._engine.begin() as conn:
            # Lock the case so two identical requests cannot both pass the idempotency check.
            conn.execute(sa.select(cases.c.id).where(cases.c.id == case_id).with_for_update()).one()
            if idempotency_key:
                existing = (
                    conn.execute(
                        sa.select(research_runs).where(
                            research_runs.c.case_id == case_id,
                            research_runs.c.idempotency_key == idempotency_key,
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing:
                    return _run(existing)
            row = (
                conn.execute(
                    sa.insert(research_runs)
                    .values(
                        id=run_id,
                        case_id=case_id,
                        tenant_id=tenant_id,
                        status="PLANNED",
                        trigger="manual",
                        jurisdictions=jurisdictions,
                        versions=versions,
                        idempotency_key=idempotency_key,
                        correlation_id=correlation_id,
                        created_by=created_by,
                        created_at=datetime.now(UTC),
                    )
                    .returning(research_runs)
                )
                .mappings()
                .one()
            )
            conn.execute(
                sa.insert(research_steps),
                [
                    {
                        "id": uuid.uuid4(),
                        "run_id": run_id,
                        "case_id": case_id,
                        "tenant_id": tenant_id,
                        "ordinal": i,
                        "category": s.category.value,
                        "source_id": uuid.UUID(s.source_id) if s.source_id else None,
                        "source_snapshot": s.source_snapshot,
                        "discovery_only": s.discovery_only,
                        "state": s.state.value,
                        "reason": s.reason,
                        "attempts": 0,
                        "max_attempts": max_attempts,
                    }
                    for i, s in enumerate(steps, start=1)
                ],
            )
        return _run(row)

    def get_run(self, run_id: uuid.UUID) -> RunRecord | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(sa.select(research_runs).where(research_runs.c.id == run_id))
                .mappings()
                .first()
            )
        return _run(row) if row else None

    def list_runs(self, case_id: uuid.UUID, tenant_id: str) -> list[RunRecord]:
        stmt = (
            sa.select(research_runs)
            .where(research_runs.c.case_id == case_id, research_runs.c.tenant_id == tenant_id)
            .order_by(research_runs.c.seq.desc())
        )
        with self._engine.connect() as conn:
            return [_run(r) for r in conn.execute(stmt).mappings().all()]

    def steps_for_run(self, run_id: uuid.UUID) -> list[StepRecord]:
        stmt = (
            sa.select(research_steps)
            .where(research_steps.c.run_id == run_id)
            .order_by(research_steps.c.ordinal)
        )
        with self._engine.connect() as conn:
            return [_step(r) for r in conn.execute(stmt).mappings().all()]

    def get_step(self, step_id: uuid.UUID) -> StepRecord | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(sa.select(research_steps).where(research_steps.c.id == step_id))
                .mappings()
                .first()
            )
        return _step(row) if row else None

    def case_of_step(self, step_id: uuid.UUID) -> uuid.UUID | None:
        with self._engine.connect() as conn:
            return conn.execute(
                sa.select(research_steps.c.case_id).where(research_steps.c.id == step_id)
            ).scalar_one_or_none()
