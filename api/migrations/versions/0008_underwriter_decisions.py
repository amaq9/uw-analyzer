"""underwriter_decisions: the human's recorded decision on a draft (ADR 0005, items 7 and 8)

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE underwriter_decisions (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            case_id uuid NOT NULL REFERENCES cases (id),
            draft_id uuid NOT NULL UNIQUE REFERENCES draft_recommendations (id),
            tenant_id text NOT NULL,
            action text NOT NULL CHECK (action IN ('ADOPT', 'CHANGE', 'REJECT')),
            final_outcome text CHECK (final_outcome IN ('APPROVE', 'DECLINE')),
            final_amount numeric(18, 2) CHECK (final_amount > 0),
            currency text CHECK (currency ~ '^[A-Z]{3}$'),
            reason text,
            agrees boolean NOT NULL,
            decided_by text NOT NULL,
            decided_at timestamptz NOT NULL,
            CONSTRAINT decision_shape CHECK (
                (action = 'REJECT' AND final_outcome IS NULL AND final_amount IS NULL
                    AND reason IS NOT NULL AND NOT agrees)
                OR (action = 'ADOPT' AND final_outcome IS NOT NULL AND agrees)
                OR (action = 'CHANGE' AND final_outcome IS NOT NULL AND reason IS NOT NULL
                    AND NOT agrees)
            ),
            CONSTRAINT decision_amount_matches_outcome CHECK (
                (final_outcome = 'APPROVE' AND final_amount IS NOT NULL)
                OR (final_outcome IS DISTINCT FROM 'APPROVE' AND final_amount IS NULL)
            )
        )
        """
    )
    op.execute("CREATE INDEX ix_underwriter_decisions_case ON underwriter_decisions (case_id, seq)")
    op.execute(
        """
        CREATE FUNCTION underwriter_decisions_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'underwriter_decisions is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER underwriter_decisions_no_update_delete
        BEFORE UPDATE OR DELETE ON underwriter_decisions
        FOR EACH ROW EXECUTE FUNCTION underwriter_decisions_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER underwriter_decisions_no_truncate
        BEFORE TRUNCATE ON underwriter_decisions
        FOR EACH STATEMENT EXECUTE FUNCTION underwriter_decisions_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE underwriter_decisions")
    op.execute("DROP FUNCTION underwriter_decisions_block_change()")
