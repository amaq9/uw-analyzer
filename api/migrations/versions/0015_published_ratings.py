"""published_ratings: agency opinions recorded on a case, each with its source (append-only)

Revision ID: 0015
Revises: 0014
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE published_ratings (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            tenant_id text NOT NULL,
            case_id uuid NOT NULL REFERENCES cases (id),
            agency text NOT NULL CHECK (agency IN ('MOODYS', 'SP', 'FITCH')),
            grade text NOT NULL,
            outlook text NOT NULL
                CHECK (outlook IN ('STABLE', 'POSITIVE', 'NEGATIVE', 'DEVELOPING', 'NOT_STATED')),
            under_review boolean NOT NULL,
            change text NOT NULL
                CHECK (change IN ('UPGRADE', 'DOWNGRADE', 'AFFIRMED', 'NEW', 'NOT_STATED')),
            last_action_on date,
            rationale text,
            -- A record without its source is not a record (P-01, P-02).
            source_url text NOT NULL CHECK (source_url ~ '^https://[^[:space:]/]+'),
            retrieved_at timestamptz NOT NULL,
            quote text NOT NULL CHECK (length(quote) BETWEEN 1 AND 300),
            recorded_by text NOT NULL,
            recorded_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_published_ratings_case ON published_ratings (case_id, agency, seq)")
    op.execute(
        """
        CREATE FUNCTION published_ratings_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'published_ratings is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER published_ratings_no_update_delete
        BEFORE UPDATE OR DELETE ON published_ratings
        FOR EACH ROW EXECUTE FUNCTION published_ratings_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER published_ratings_no_truncate
        BEFORE TRUNCATE ON published_ratings
        FOR EACH STATEMENT EXECUTE FUNCTION published_ratings_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE published_ratings")
    op.execute("DROP FUNCTION published_ratings_block_change()")
