"""case_documents: uploaded document metadata (FR-1.2)

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE case_documents (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            case_id uuid NOT NULL REFERENCES cases (id),
            tenant_id text NOT NULL,
            category text NOT NULL
                CHECK (category IN ('financial_statement', 'credit_report', 'supporting')),
            original_filename text NOT NULL,
            content_type text NOT NULL,
            size_bytes bigint NOT NULL CHECK (size_bytes > 0),
            sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
            storage_key text NOT NULL UNIQUE,
            scan_status text NOT NULL CHECK (scan_status IN ('clean')),
            scanned_at timestamptz NOT NULL,
            uploaded_by text NOT NULL,
            uploaded_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_case_documents_case ON case_documents (case_id, seq)")
    # Uploaded documents are evidence the research relies on: their records cannot be edited or
    # removed (a retention and deletion policy will define a controlled path later).
    op.execute(
        """
        CREATE FUNCTION case_documents_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'case_documents is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER case_documents_no_update_delete
        BEFORE UPDATE OR DELETE ON case_documents
        FOR EACH ROW EXECUTE FUNCTION case_documents_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER case_documents_no_truncate
        BEFORE TRUNCATE ON case_documents
        FOR EACH STATEMENT EXECUTE FUNCTION case_documents_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE case_documents")
    op.execute("DROP FUNCTION case_documents_block_change()")
