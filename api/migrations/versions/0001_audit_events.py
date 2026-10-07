"""audit_events: append-only audit table (FR-0.5)

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_events (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            occurred_at timestamptz NOT NULL,
            tenant_id text,
            actor text,
            action text NOT NULL,
            outcome text NOT NULL,
            resource_type text,
            resource_id text,
            correlation_id text NOT NULL,
            details jsonb NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute("CREATE INDEX ix_audit_events_tenant_seq ON audit_events (tenant_id, seq DESC)")
    op.execute("CREATE INDEX ix_audit_events_correlation ON audit_events (correlation_id)")
    op.execute(
        """
        CREATE FUNCTION audit_events_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_truncate
        BEFORE TRUNCATE ON audit_events
        FOR EACH STATEMENT EXECUTE FUNCTION audit_events_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE audit_events")
    op.execute("DROP FUNCTION audit_events_block_change()")
