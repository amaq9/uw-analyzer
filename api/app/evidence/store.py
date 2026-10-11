import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Engine

from app.cases.store import cases
from app.evidence.rules import Relation
from app.evidence.schemas import ClaimRecord, EvidenceRecord, LinkRecord

metadata = sa.MetaData()
evidence = sa.Table(
    "evidence",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("evidence_type", sa.Text, nullable=False),
    sa.Column("source_class", sa.Text, nullable=False),
    sa.Column("class_basis", sa.Text, nullable=False),
    sa.Column("source_id", UUID(as_uuid=True)),
    sa.Column("connector_call_id", UUID(as_uuid=True)),
    sa.Column("document_id", UUID(as_uuid=True)),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("origin", sa.Text, nullable=False),
    sa.Column("url", sa.Text),
    sa.Column("published_on", sa.Date),
    sa.Column("event_on", sa.Date),
    sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("excerpt", sa.Text, nullable=False),
    sa.Column("provenance_ref", sa.Text),
    sa.Column("content_hash", sa.Text),
    sa.Column("is_primary", sa.Boolean, nullable=False),
    sa.Column("discovery_only", sa.Boolean, nullable=False),
    sa.Column("created_by", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
claims = sa.Table(
    "claims",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("classification", sa.Text, nullable=False),
    sa.Column("material", sa.Boolean, nullable=False),
    sa.Column("adverse", sa.Boolean, nullable=False),
    sa.Column("credit_relevance", sa.Text),
    sa.Column("category", sa.Text),
    sa.Column("unavailable_step_id", UUID(as_uuid=True)),
    sa.Column("created_by", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
claim_basis = sa.Table(
    "claim_basis",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("claim_id", UUID(as_uuid=True), primary_key=True),
    sa.Column("basis_claim_id", UUID(as_uuid=True), primary_key=True),
)
claim_evidence = sa.Table(
    "claim_evidence",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("claim_id", UUID(as_uuid=True), nullable=False),
    sa.Column("evidence_id", UUID(as_uuid=True), nullable=False),
    sa.Column("relation", sa.Text, nullable=False),
    sa.Column("notes", sa.Text),
    sa.Column("created_by", sa.Text, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


def _strip(row: sa.RowMapping) -> dict[str, Any]:
    data = dict(row)
    data.pop("seq", None)
    return data


class DuplicateLinkError(Exception):
    pass


class PostgresEvidenceStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # --- evidence -------------------------------------------------------------------------
    def add_evidence(self, values: dict[str, Any]) -> EvidenceRecord:
        stmt = (
            sa.insert(evidence)
            .values(id=uuid.uuid4(), created_at=datetime.now(UTC), **values)
            .returning(evidence)
        )
        with self._engine.begin() as conn:
            return EvidenceRecord(**_strip(conn.execute(stmt).mappings().one()))

    def get_evidence(self, evidence_id: uuid.UUID) -> EvidenceRecord | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(sa.select(evidence).where(evidence.c.id == evidence_id))
                .mappings()
                .first()
            )
        return EvidenceRecord(**_strip(row)) if row else None

    def list_evidence(self, case_id: uuid.UUID, tenant_id: str) -> list[EvidenceRecord]:
        stmt = (
            sa.select(evidence)
            .where(evidence.c.case_id == case_id, evidence.c.tenant_id == tenant_id)
            .order_by(evidence.c.seq.desc())
        )
        with self._engine.connect() as conn:
            return [EvidenceRecord(**_strip(r)) for r in conn.execute(stmt).mappings().all()]

    # --- claims ---------------------------------------------------------------------------
    def add_claim(
        self,
        values: dict[str, Any],
        basis: list[uuid.UUID],
        links: list[tuple[uuid.UUID, Relation, str | None]],
    ) -> ClaimRecord:
        """Create a claim, its basis and its evidence links in one transaction."""
        now = datetime.now(UTC)
        claim_id = uuid.uuid4()
        with self._engine.begin() as conn:
            conn.execute(
                sa.select(cases.c.id).where(cases.c.id == values["case_id"]).with_for_update()
            ).one()
            row = (
                conn.execute(
                    sa.insert(claims)
                    .values(id=claim_id, created_at=now, **values)
                    .returning(claims)
                )
                .mappings()
                .one()
            )
            if basis:
                conn.execute(
                    sa.insert(claim_basis),
                    [{"claim_id": claim_id, "basis_claim_id": b} for b in basis],
                )
            if links:
                conn.execute(
                    sa.insert(claim_evidence),
                    [
                        {
                            "id": uuid.uuid4(),
                            "claim_id": claim_id,
                            "evidence_id": ev,
                            "relation": rel.value,
                            "notes": notes,
                            "created_by": values["created_by"],
                            "created_at": now,
                        }
                        for ev, rel, notes in links
                    ],
                )
        return ClaimRecord(**_strip(row))

    def add_link(
        self,
        claim_id: uuid.UUID,
        evidence_id: uuid.UUID,
        relation: Relation,
        notes: str | None,
        created_by: str,
    ) -> LinkRecord:
        stmt = (
            sa.insert(claim_evidence)
            .values(
                id=uuid.uuid4(),
                claim_id=claim_id,
                evidence_id=evidence_id,
                relation=relation.value,
                notes=notes,
                created_by=created_by,
                created_at=datetime.now(UTC),
            )
            .returning(claim_evidence)
        )
        try:
            with self._engine.begin() as conn:
                return LinkRecord(**_strip(conn.execute(stmt).mappings().one()))
        except sa.exc.IntegrityError as exc:
            if "claim_evidence_claim_id_evidence_id_key" in str(exc.orig):
                raise DuplicateLinkError from None
            raise

    def get_claim(self, claim_id: uuid.UUID) -> ClaimRecord | None:
        with self._engine.connect() as conn:
            row = conn.execute(sa.select(claims).where(claims.c.id == claim_id)).mappings().first()
        return ClaimRecord(**_strip(row)) if row else None

    def list_claims(self, case_id: uuid.UUID, tenant_id: str) -> list[ClaimRecord]:
        stmt = (
            sa.select(claims)
            .where(claims.c.case_id == case_id, claims.c.tenant_id == tenant_id)
            .order_by(claims.c.seq)
        )
        with self._engine.connect() as conn:
            return [ClaimRecord(**_strip(r)) for r in conn.execute(stmt).mappings().all()]

    def basis_of(self, claim_id: uuid.UUID) -> list[uuid.UUID]:
        stmt = (
            sa.select(claim_basis.c.basis_claim_id)
            .where(claim_basis.c.claim_id == claim_id)
            .order_by(claim_basis.c.seq)
        )
        with self._engine.connect() as conn:
            return [r[0] for r in conn.execute(stmt).all()]

    def links_of(self, claim_id: uuid.UUID) -> list[LinkRecord]:
        stmt = (
            sa.select(claim_evidence)
            .where(claim_evidence.c.claim_id == claim_id)
            .order_by(claim_evidence.c.seq)
        )
        with self._engine.connect() as conn:
            return [LinkRecord(**_strip(r)) for r in conn.execute(stmt).mappings().all()]
