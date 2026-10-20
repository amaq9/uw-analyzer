"""Queue and execution bookkeeping for research runs. Postgres is the queue: a worker claims a
QUEUED run with SELECT ... FOR UPDATE SKIP LOCKED, so two workers never take the same run and a
crash leaves the run in the database to be resumed."""

import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Engine

from app.research.schemas import CallRecord, RunRecord
from app.research.store import _run, research_runs, research_steps

metadata = sa.MetaData()
connector_calls = sa.Table(
    "connector_calls",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("run_id", UUID(as_uuid=True), nullable=False),
    sa.Column("step_id", UUID(as_uuid=True), nullable=False),
    sa.Column("source_id", UUID(as_uuid=True), nullable=False),
    sa.Column("source_key", sa.Text, nullable=False),
    sa.Column("connector_version", sa.Text, nullable=False),
    sa.Column("attempt", sa.Integer, nullable=False),
    sa.Column("action", sa.Text, nullable=False),
    sa.Column("access_status", sa.Text, nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("outcome", sa.Text, nullable=False),
    sa.Column("error_class", sa.Text),
    sa.Column("provenance_ref", sa.Text),
)


def _call(row: sa.RowMapping) -> CallRecord:
    data = dict(row)
    data.pop("seq")
    return CallRecord(**data)


class PostgresRunQueue:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def queue(self, run_id: uuid.UUID) -> bool:
        """PLANNED, FAILED, or COMPLETED with a failed step (a discovery-only source that could not
        be reached) -> QUEUED. False if the run is in any other state."""
        has_failed_step = (
            sa.select(research_steps.c.id)
            .where(research_steps.c.run_id == run_id, research_steps.c.state == "FAILED")
            .exists()
        )
        stmt = (
            sa.update(research_runs)
            .where(
                research_runs.c.id == run_id,
                sa.or_(
                    research_runs.c.status.in_(("PLANNED", "FAILED")),
                    sa.and_(research_runs.c.status == "COMPLETED", has_failed_step),
                ),
            )
            .values(status="QUEUED", completed_at=None)
        )
        with self._engine.begin() as conn:
            if conn.execute(stmt).rowcount != 1:
                return False
            # A resumed run gives failed steps a fresh budget of attempts (the call log keeps
            # every earlier attempt, so attempt numbers continue).
            conn.execute(
                sa.update(research_steps)
                .where(research_steps.c.run_id == run_id, research_steps.c.state == "FAILED")
                .values(
                    state="PLANNED",
                    error_class=None,
                    finished_at=None,
                    max_attempts=research_steps.c.attempts + 3,
                )
            )
            return True

    def claim_next(self) -> RunRecord | None:
        """Take the oldest QUEUED run and mark it RUNNING. Steps left RUNNING by a crashed worker
        go back to PLANNED so the run resumes where it stopped."""
        with self._engine.begin() as conn:
            row = (
                conn.execute(
                    sa.select(research_runs)
                    .where(research_runs.c.status == "QUEUED")
                    .order_by(research_runs.c.seq)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            claimed = (
                conn.execute(
                    sa.update(research_runs)
                    .where(research_runs.c.id == row["id"])
                    .values(
                        status="RUNNING",
                        started_at=sa.func.coalesce(research_runs.c.started_at, datetime.now(UTC)),
                    )
                    .returning(research_runs)
                )
                .mappings()
                .one()
            )
            conn.execute(
                sa.update(research_steps)
                .where(research_steps.c.run_id == row["id"], research_steps.c.state == "RUNNING")
                .values(state="PLANNED")
            )
        return _run(claimed)

    def finish_run(self, run_id: uuid.UUID, status: str, versions: dict[str, Any]) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                sa.update(research_runs)
                .where(research_runs.c.id == run_id)
                .values(status=status, completed_at=datetime.now(UTC), versions=versions)
            )

    def mark_step(
        self,
        step_id: uuid.UUID,
        state: str,
        *,
        reason: str | None = None,
        attempts: int | None = None,
        error_class: str | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> None:
        values: dict[str, Any] = {"state": state, "error_class": error_class}
        if reason is not None:
            values["reason"] = reason
        if attempts is not None:
            values["attempts"] = attempts
        now = datetime.now(UTC)
        if started:
            values["started_at"] = sa.func.coalesce(research_steps.c.started_at, now)
        if finished:
            values["finished_at"] = now
        with self._engine.begin() as conn:
            conn.execute(
                sa.update(research_steps).where(research_steps.c.id == step_id).values(**values)
            )

    def add_call(self, **values: Any) -> CallRecord:
        stmt = (
            sa.insert(connector_calls).values(id=uuid.uuid4(), **values).returning(connector_calls)
        )
        with self._engine.begin() as conn:
            return _call(conn.execute(stmt).mappings().one())

    def calls_for_run(self, run_id: uuid.UUID) -> list[CallRecord]:
        stmt = (
            sa.select(connector_calls)
            .where(connector_calls.c.run_id == run_id)
            .order_by(connector_calls.c.seq)
        )
        with self._engine.connect() as conn:
            return [_call(r) for r in conn.execute(stmt).mappings().all()]

    def get_call(self, call_id: uuid.UUID) -> CallRecord | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(sa.select(connector_calls).where(connector_calls.c.id == call_id))
                .mappings()
                .first()
            )
        return _call(row) if row else None
