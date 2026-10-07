"""draft_recommendations: system or assisted drafts for the underwriter (ADR 0005, ADR 0008)

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE draft_recommendations (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            case_id uuid NOT NULL REFERENCES cases (id),
            tenant_id text NOT NULL,
            version integer NOT NULL CHECK (version >= 1),
            outcome text NOT NULL CHECK (outcome IN ('APPROVE', 'DECLINE')),
            band text NOT NULL CHECK (band IN ('FULL', 'REDUCED', 'DECLINE')),
            requested_amount numeric(18, 2),
            requested_currency text CHECK (requested_currency ~ '^[A-Z]{3}$'),
            recommended_amount numeric(18, 2) CHECK (recommended_amount > 0),
            ai_proposed_amount numeric(18, 2) CHECK (ai_proposed_amount >= 0),
            rule_codes jsonb NOT NULL,
            content jsonb NOT NULL,
            source jsonb NOT NULL,
            policy_version text NOT NULL,
            created_by text NOT NULL,
            created_at timestamptz NOT NULL,
            UNIQUE (case_id, version),
            CONSTRAINT draft_outcome_matches_band CHECK (
                (outcome = 'DECLINE' AND band = 'DECLINE' AND recommended_amount IS NULL)
                OR (outcome = 'APPROVE' AND band IN ('FULL', 'REDUCED')
                    AND recommended_amount IS NOT NULL)
            ),
            CONSTRAINT draft_never_above_request CHECK (
                recommended_amount IS NULL OR requested_amount IS NULL
                OR recommended_amount <= requested_amount
            )
        )
        """
    )
    op.execute("CREATE INDEX ix_draft_recommendations_case ON draft_recommendations (case_id, seq)")
    # A draft is a record of what the analysis said at the time: it can never be edited or removed.
    op.execute(
        """
        CREATE FUNCTION draft_recommendations_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'draft_recommendations is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER draft_recommendations_no_update_delete
        BEFORE UPDATE OR DELETE ON draft_recommendations
        FOR EACH ROW EXECUTE FUNCTION draft_recommendations_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER draft_recommendations_no_truncate
        BEFORE TRUNCATE ON draft_recommendations
        FOR EACH STATEMENT EXECUTE FUNCTION draft_recommendations_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE draft_recommendations")
    op.execute("DROP FUNCTION draft_recommendations_block_change()")
