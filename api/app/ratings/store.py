import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Engine

from app.cases.store import cases
from app.ratings.schemas import PublishedRatingIn, PublishedRatingRecord

metadata = sa.MetaData()
published_ratings = sa.Table(
    "published_ratings",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("agency", sa.Text, nullable=False),
    sa.Column("grade", sa.Text, nullable=False),
    sa.Column("outlook", sa.Text, nullable=False),
    sa.Column("under_review", sa.Boolean, nullable=False),
    sa.Column("change", sa.Text, nullable=False),
    sa.Column("last_action_on", sa.Date),
    sa.Column("rationale", sa.Text),
    sa.Column("source_url", sa.Text, nullable=False),
    sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("quote", sa.Text, nullable=False),
    sa.Column("recorded_by", sa.Text, nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
)


def _record(row: sa.RowMapping) -> PublishedRatingRecord:
    data = dict(row)
    data.pop("seq")
    return PublishedRatingRecord(**data)


class PostgresRatingStore:
    """Append-only: a newer record for an agency supersedes the older one for analysis, and the
    older one stays on record."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(
        self, *, tenant_id: str, case_id: uuid.UUID, body: PublishedRatingIn, recorded_by: str
    ) -> PublishedRatingRecord:
        with self._engine.begin() as conn:
            conn.execute(sa.select(cases.c.id).where(cases.c.id == case_id).with_for_update()).one()
            row = (
                conn.execute(
                    sa.insert(published_ratings)
                    .values(
                        id=uuid.uuid4(),
                        tenant_id=tenant_id,
                        case_id=case_id,
                        agency=body.agency,
                        grade=body.grade,
                        outlook=body.outlook,
                        under_review=body.under_review,
                        change=body.change,
                        last_action_on=body.last_action_on,
                        rationale=body.rationale,
                        source_url=body.source_url,
                        retrieved_at=body.retrieved_at,
                        quote=body.quote,
                        recorded_by=recorded_by,
                        recorded_at=datetime.now(UTC),
                    )
                    .returning(published_ratings)
                )
                .mappings()
                .one()
            )
        return _record(row)

    def list_for_case(self, case_id: uuid.UUID, tenant_id: str) -> list[PublishedRatingRecord]:
        """Every record, newest first."""
        stmt = (
            sa.select(published_ratings)
            .where(
                published_ratings.c.case_id == case_id, published_ratings.c.tenant_id == tenant_id
            )
            .order_by(published_ratings.c.seq.desc())
        )
        with self._engine.connect() as conn:
            return [_record(r) for r in conn.execute(stmt).mappings().all()]

    def latest_per_agency(self, case_id: uuid.UUID, tenant_id: str) -> list[PublishedRatingRecord]:
        """The most recently recorded opinion of each agency, in the order Moody's, S&P, Fitch."""
        latest: dict[str, PublishedRatingRecord] = {}
        for record in self.list_for_case(case_id, tenant_id):
            latest.setdefault(record.agency, record)
        order = {"MOODYS": 0, "SP": 1, "FITCH": 2}
        return sorted(latest.values(), key=lambda r: order[r.agency])
