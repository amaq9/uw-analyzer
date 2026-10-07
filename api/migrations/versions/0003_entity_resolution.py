"""entity resolution: candidates, resolution log, resolved fields on cases (FR-1.4 to FR-1.6)

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE cases
            ADD COLUMN resolved_candidate_id uuid,
            ADD COLUMN resolved_by text,
            ADD COLUMN resolved_at timestamptz
        """
    )
    op.execute(
        """
        CREATE TABLE entity_candidates (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            case_id uuid NOT NULL REFERENCES cases (id),
            tenant_id text NOT NULL,
            state text NOT NULL DEFAULT 'candidate'
                CHECK (state IN ('candidate', 'selected', 'rejected')),
            source text NOT NULL DEFAULT 'user_entered' CHECK (source IN ('user_entered')),
            legal_name text NOT NULL,
            registration_number text,
            jurisdiction text,
            address text,
            website text,
            parent_name text,
            aliases text[] NOT NULL DEFAULT '{}',
            former_names text[] NOT NULL DEFAULT '{}',
            subsidiaries text[] NOT NULL DEFAULT '{}',
            created_by text NOT NULL,
            created_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_entity_candidates_case ON entity_candidates (case_id, seq)")
    op.execute(
        """
        CREATE TABLE entity_resolution_log (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            case_id uuid NOT NULL REFERENCES cases (id),
            tenant_id text NOT NULL,
            action text NOT NULL CHECK (action IN ('resolved', 'reopened')),
            candidate_id uuid,
            actor text NOT NULL,
            note text,
            occurred_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_entity_resolution_log_case ON entity_resolution_log (case_id, seq)")
    # The record of who resolved or reopened an entity, and why, can never be edited (P-07).
    op.execute(
        """
        CREATE FUNCTION entity_resolution_log_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'entity_resolution_log is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER entity_resolution_log_no_update_delete
        BEFORE UPDATE OR DELETE ON entity_resolution_log
        FOR EACH ROW EXECUTE FUNCTION entity_resolution_log_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER entity_resolution_log_no_truncate
        BEFORE TRUNCATE ON entity_resolution_log
        FOR EACH STATEMENT EXECUTE FUNCTION entity_resolution_log_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE entity_resolution_log")
    op.execute("DROP FUNCTION entity_resolution_log_block_change()")
    op.execute("DROP TABLE entity_candidates")
    op.execute(
        "ALTER TABLE cases DROP COLUMN resolved_candidate_id, DROP COLUMN resolved_by, "
        "DROP COLUMN resolved_at"
    )
