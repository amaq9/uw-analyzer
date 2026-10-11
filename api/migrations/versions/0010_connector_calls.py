"""connector_calls: every executed connector call, append-only (FR-2.6, FR-2.7, P-01)

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE connector_calls (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            tenant_id text NOT NULL,
            case_id uuid NOT NULL REFERENCES cases (id),
            run_id uuid NOT NULL REFERENCES research_runs (id),
            step_id uuid NOT NULL REFERENCES research_steps (id),
            source_id uuid NOT NULL REFERENCES sources (id),
            source_key text NOT NULL,
            connector_version text NOT NULL,
            attempt integer NOT NULL CHECK (attempt >= 1),
            action text NOT NULL,
            access_status text NOT NULL CHECK (access_status IN (
                'ACTUALLY_ACCESSIBLE', 'RESTRICTED_LICENSED', 'DISCOVERY_ONLY',
                'TECHNICALLY_UNAVAILABLE')),
            started_at timestamptz NOT NULL,
            ended_at timestamptz NOT NULL,
            outcome text NOT NULL CHECK (outcome IN ('SUCCESS', 'ERROR', 'TIMEOUT')),
            error_class text,
            provenance_ref text,
            -- Access can only be recorded together with a returned provenance reference.
            CONSTRAINT success_has_provenance CHECK (
                outcome <> 'SUCCESS' OR (provenance_ref IS NOT NULL AND provenance_ref <> '')
            ),
            UNIQUE (step_id, attempt)
        )
        """
    )
    op.execute("CREATE INDEX ix_connector_calls_run ON connector_calls (run_id, seq)")
    op.execute(
        """
        CREATE FUNCTION connector_calls_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'connector_calls is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER connector_calls_no_update_delete
        BEFORE UPDATE OR DELETE ON connector_calls
        FOR EACH ROW EXECUTE FUNCTION connector_calls_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER connector_calls_no_truncate
        BEFORE TRUNCATE ON connector_calls
        FOR EACH STATEMENT EXECUTE FUNCTION connector_calls_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE connector_calls")
    op.execute("DROP FUNCTION connector_calls_block_change()")
