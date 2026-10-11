"""escalations and escalation_resolutions: human review that cannot be auto-closed (P-07)

Revision ID: 0012
Revises: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE escalations (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            tenant_id text NOT NULL,
            case_id uuid NOT NULL REFERENCES cases (id),
            kind text NOT NULL CHECK (kind IN ('CONFLICT', 'MATERIAL_AMBIGUITY', 'OTHER')),
            claim_id uuid REFERENCES claims (id),
            description text NOT NULL,
            raised_by_system boolean NOT NULL,
            created_by text NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT conflict_has_claim CHECK (kind <> 'CONFLICT' OR claim_id IS NOT NULL)
        )
        """
    )
    op.execute("CREATE INDEX ix_escalations_case ON escalations (case_id, seq)")
    op.execute(
        """
        CREATE TABLE escalation_resolutions (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            escalation_id uuid NOT NULL UNIQUE REFERENCES escalations (id),
            tenant_id text NOT NULL,
            outcome text NOT NULL CHECK (outcome IN (
                'SUPPORTING_PREVAILS', 'CONTRADICTING_PREVAILS', 'NO_CLAIM_CHANGE')),
            preferred_evidence_id uuid REFERENCES evidence (id),
            explanation text NOT NULL CHECK (length(trim(explanation)) > 0),
            resolved_by text NOT NULL,
            resolved_at timestamptz NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION escalation_tables_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER escalations_no_update_delete
        BEFORE UPDATE OR DELETE ON escalations
        FOR EACH ROW EXECUTE FUNCTION escalation_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER escalations_no_truncate
        BEFORE TRUNCATE ON escalations
        FOR EACH STATEMENT EXECUTE FUNCTION escalation_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER escalation_resolutions_no_update_delete
        BEFORE UPDATE OR DELETE ON escalation_resolutions
        FOR EACH ROW EXECUTE FUNCTION escalation_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER escalation_resolutions_no_truncate
        BEFORE TRUNCATE ON escalation_resolutions
        FOR EACH STATEMENT EXECUTE FUNCTION escalation_tables_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE escalation_resolutions")
    op.execute("DROP TABLE escalations")
    op.execute("DROP FUNCTION escalation_tables_block_change()")
