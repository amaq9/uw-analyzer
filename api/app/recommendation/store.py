import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.engine import Engine

from app.cases.store import cases
from app.recommendation.policy import Band, Outcome
from app.recommendation.schemas import DraftRecord

metadata = sa.MetaData()
draft_recommendations = sa.Table(
    "draft_recommendations",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("outcome", sa.Text, nullable=False),
    sa.Column("band", sa.Text, nullable=False),
    sa.Column("requested_amount", sa.Numeric(18, 2)),
    sa.Column("requested_currency", sa.Text),
    sa.Column("recommended_amount", sa.Numeric(18, 2)),
    sa.Column("ai_proposed_amount", sa.Numeric(18, 2)),
    sa.Column("rule_codes", JSONB, nullable=False),
    sa.Column("content", JSONB, nullable=False),
    sa.Column("source", JSONB, nullable=False),
    sa.Column("policy_version", sa.Text, nullable=False),
    sa.Column("created_by", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


def _record(row: sa.RowMapping) -> DraftRecord:
    data = dict(row)
    data.pop("seq")
    return DraftRecord(**data)


class PostgresDraftStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(
        self,
        *,
        case_id: uuid.UUID,
        tenant_id: str,
        outcome: Outcome,
        band: Band,
        requested_amount: Decimal | None,
        requested_currency: str | None,
        recommended_amount: Decimal | None,
        ai_proposed_amount: Decimal | None,
        rule_codes: list[str],
        content: dict[str, Any],
        source: dict[str, Any],
        policy_version: str,
        created_by: str,
    ) -> DraftRecord:
        with self._engine.begin() as conn:
            # Lock the case so two drafts cannot receive the same version number.
            conn.execute(sa.select(cases.c.id).where(cases.c.id == case_id).with_for_update()).one()
            version = (
                conn.execute(
                    sa.select(
                        sa.func.coalesce(sa.func.max(draft_recommendations.c.version), 0)
                    ).where(draft_recommendations.c.case_id == case_id)
                ).scalar_one()
                + 1
            )
            row = (
                conn.execute(
                    sa.insert(draft_recommendations)
                    .values(
                        id=uuid.uuid4(),
                        case_id=case_id,
                        tenant_id=tenant_id,
                        version=version,
                        outcome=outcome.value,
                        band=band.value,
                        requested_amount=requested_amount,
                        requested_currency=requested_currency,
                        recommended_amount=recommended_amount,
                        ai_proposed_amount=ai_proposed_amount,
                        rule_codes=rule_codes,
                        content=content,
                        source=source,
                        policy_version=policy_version,
                        created_by=created_by,
                        created_at=datetime.now(UTC),
                    )
                    .returning(draft_recommendations)
                )
                .mappings()
                .one()
            )
        return _record(row)

    def get(self, draft_id: uuid.UUID) -> DraftRecord | None:
        stmt = sa.select(draft_recommendations).where(draft_recommendations.c.id == draft_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _record(row) if row else None

    def list_for_case(self, case_id: uuid.UUID, tenant_id: str) -> list[DraftRecord]:
        stmt = (
            sa.select(draft_recommendations)
            .where(
                draft_recommendations.c.case_id == case_id,
                draft_recommendations.c.tenant_id == tenant_id,
            )
            .order_by(draft_recommendations.c.seq.desc())
        )
        with self._engine.connect() as conn:
            return [_record(r) for r in conn.execute(stmt).mappings().all()]
