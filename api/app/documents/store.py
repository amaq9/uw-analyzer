import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.engine import Engine

from app.documents.schemas import DocumentCategory, DocumentRecord

metadata = sa.MetaData()
case_documents = sa.Table(
    "case_documents",
    metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(always=True), unique=True),
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("case_id", UUID(as_uuid=True), nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("category", sa.Text, nullable=False),
    sa.Column("original_filename", sa.Text, nullable=False),
    sa.Column("content_type", sa.Text, nullable=False),
    sa.Column("size_bytes", sa.BigInteger, nullable=False),
    sa.Column("sha256", sa.Text, nullable=False),
    sa.Column("storage_key", sa.Text, nullable=False),
    sa.Column("scan_status", sa.Text, nullable=False),
    sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("uploaded_by", sa.Text, nullable=False),
    sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
)


def _record(row: sa.RowMapping) -> DocumentRecord:
    data = dict(row)
    data.pop("seq")
    data["filename"] = data.pop("original_filename")
    data.pop("scanned_at")
    return DocumentRecord(**data)


class PostgresDocumentStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def count_for_case(self, case_id: uuid.UUID) -> int:
        stmt = (
            sa.select(sa.func.count())
            .select_from(case_documents)
            .where(case_documents.c.case_id == case_id)
        )
        with self._engine.connect() as conn:
            return int(conn.execute(stmt).scalar_one())

    def add(
        self,
        *,
        case_id: uuid.UUID,
        tenant_id: str,
        category: DocumentCategory,
        filename: str,
        content_type: str,
        size_bytes: int,
        sha256: str,
        storage_key: str,
        uploaded_by: str,
    ) -> DocumentRecord:
        now = datetime.now(UTC)
        stmt = (
            sa.insert(case_documents)
            .values(
                id=uuid.uuid4(),
                case_id=case_id,
                tenant_id=tenant_id,
                category=category.value,
                original_filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
                sha256=sha256,
                storage_key=storage_key,
                scan_status="clean",
                scanned_at=now,
                uploaded_by=uploaded_by,
                uploaded_at=now,
            )
            .returning(case_documents)
        )
        with self._engine.begin() as conn:
            return _record(conn.execute(stmt).mappings().one())

    def get(self, document_id: uuid.UUID) -> DocumentRecord | None:
        stmt = sa.select(case_documents).where(case_documents.c.id == document_id)
        with self._engine.connect() as conn:
            row = conn.execute(stmt).mappings().first()
        return _record(row) if row else None

    def list_for_case(self, case_id: uuid.UUID, tenant_id: str) -> list[DocumentRecord]:
        stmt = (
            sa.select(case_documents)
            .where(case_documents.c.case_id == case_id, case_documents.c.tenant_id == tenant_id)
            .order_by(case_documents.c.seq)
        )
        with self._engine.connect() as conn:
            return [_record(r) for r in conn.execute(stmt).mappings().all()]
