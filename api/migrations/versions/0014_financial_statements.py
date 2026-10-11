"""financial_statements: figures a person confirmed from an uploaded document (append-only)

Revision ID: 0014
Revises: 0013
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE financial_statements (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            tenant_id text NOT NULL,
            case_id uuid NOT NULL REFERENCES cases (id),
            document_id uuid NOT NULL REFERENCES case_documents (id),
            period_end date NOT NULL,
            currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
            unit text NOT NULL CHECK (unit IN ('units', 'thousands', 'millions')),
            audit_status text NOT NULL CHECK (audit_status IN ('AUDITED', 'REVIEWED', 'UNAUDITED')),
            figures jsonb NOT NULL,
            notes text,
            confirmed_by text NOT NULL,
            confirmed_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_fin_statements_case ON financial_statements (case_id, period_end)")
    op.execute(
        """
        CREATE FUNCTION financial_statements_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'financial_statements is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER financial_statements_no_update_delete
        BEFORE UPDATE OR DELETE ON financial_statements
        FOR EACH ROW EXECUTE FUNCTION financial_statements_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER financial_statements_no_truncate
        BEFORE TRUNCATE ON financial_statements
        FOR EACH STATEMENT EXECUTE FUNCTION financial_statements_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE financial_statements")
    op.execute("DROP FUNCTION financial_statements_block_change()")
