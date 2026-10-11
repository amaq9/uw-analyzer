import uuid
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.recommendation.decision_schemas import DecisionAction, DecisionRecord
from app.recommendation.policy import Outcome

metadata = sa.MetaData()
underwriter_decisions = sa.Table(
    "underwriter_decisions",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("action", sa.Text, nullable=False),
    sa.Column("final_outcome", sa.Text),
    sa.Column("final_amount", sa.Numeric(18, 2)),
    sa.Column("currency", sa.Text),
    sa.Column("reason", sa.Text),
    sa.Column("agrees", sa.Boolean, nullable=False),
    sa.Column("decided_by", sa.Text, nullable=False),
    sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
)


class AlreadyDecidedError(Exception):
    pass


def _record(row: sa.RowMapping) -> DecisionRecord:
    data = dict(row)
    data.pop("seq")
    return DecisionRecord(**data)


class PostgresDecisionStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(
        self,
        *,
        case_id: uuid.UUID,
        draft_id: uuid.UUID,
        tenant_id: str,
        action: DecisionAction,
        final_outcome: Outcome | None,
        final_amount: Decimal | None,
        currency: str | None,
        reason: str | None,
        agrees: bool,
        decided_by: str,
    ) -> DecisionRecord:
        stmt = (
            sa.insert(underwriter_decisions)
            .values(
                id=uuid.uuid4(),
                case_id=case_id,
                draft_id=draft_id,
                tenant_id=tenant_id,
                action=action.value,
                final_outcome=final_outcome.value if final_outcome else None,
                final_amount=final_amount,
                currency=currency,
                reason=reason,
                agrees=agrees,
                decided_by=decided_by,
                decided_at=datetime.now(UTC),
            )
            .returning(underwriter_decisions)
        )
        try:
            with self._engine.begin() as conn:
                return _record(conn.execute(stmt).mappings().one())
        except IntegrityError as exc:
            if "underwriter_decisions_draft_id_key" in str(exc.orig):
                raise AlreadyDecidedError from None
            raise

    def get_for_draft(self, draft_id: uuid.UUID) -> DecisionRecord | None:
        stmt = sa.select(underwriter_decisions).where(underwriter_decisions.c.draft_id == draft_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _record(row) if row else None
