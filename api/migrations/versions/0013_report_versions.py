"""report_versions: immutable research report versions (P-08)

Revision ID: 0013
Revises: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE report_versions (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            tenant_id text NOT NULL,
            case_id uuid NOT NULL REFERENCES cases (id),
            version integer NOT NULL CHECK (version >= 1),
            note text,
            content jsonb NOT NULL,
            content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            versions jsonb NOT NULL,
            created_by text NOT NULL,
            created_at timestamptz NOT NULL,
            UNIQUE (case_id, version)
        )
        """
    )
    op.execute("CREATE INDEX ix_report_versions_case ON report_versions (case_id, version)")
    op.execute(
        """
        CREATE FUNCTION report_versions_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'report_versions is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER report_versions_no_update_delete
        BEFORE UPDATE OR DELETE ON report_versions
        FOR EACH ROW EXECUTE FUNCTION report_versions_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER report_versions_no_truncate
        BEFORE TRUNCATE ON report_versions
        FOR EACH STATEMENT EXECUTE FUNCTION report_versions_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE report_versions")
    op.execute("DROP FUNCTION report_versions_block_change()")
