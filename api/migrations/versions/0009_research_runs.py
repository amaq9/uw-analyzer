"""research_runs and research_steps: planned research per case (FR-2.3, FR-2.5, P-10)

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE research_runs (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            case_id uuid NOT NULL REFERENCES cases (id),
            tenant_id text NOT NULL,
            status text NOT NULL CHECK (status IN (
                'PLANNED', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
            trigger text NOT NULL CHECK (trigger IN ('manual')),
            jurisdictions text[] NOT NULL CHECK (cardinality(jurisdictions) >= 1),
            versions jsonb NOT NULL,
            idempotency_key text,
            correlation_id text NOT NULL,
            created_by text NOT NULL,
            created_at timestamptz NOT NULL,
            started_at timestamptz,
            completed_at timestamptz,
            UNIQUE (case_id, idempotency_key)
        )
        """
    )
    op.execute("CREATE INDEX ix_research_runs_case ON research_runs (case_id, seq)")
    op.execute(
        """
        CREATE TABLE research_steps (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            run_id uuid NOT NULL REFERENCES research_runs (id),
            case_id uuid NOT NULL REFERENCES cases (id),
            tenant_id text NOT NULL,
            ordinal integer NOT NULL,
            category text NOT NULL CHECK (category IN (
                'ENTITY_REGISTRY', 'FINANCIALS', 'ADVERSE_SEARCH', 'COUNTRY_INDUSTRY')),
            source_id uuid REFERENCES sources (id),
            source_snapshot jsonb NOT NULL,
            discovery_only boolean NOT NULL DEFAULT false,
            state text NOT NULL CHECK (state IN (
                'PLANNED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'NOT_AVAILABLE', 'SKIPPED')),
            reason text,
            attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
            max_attempts integer NOT NULL DEFAULT 3 CHECK (max_attempts >= 1),
            error_class text,
            started_at timestamptz,
            finished_at timestamptz,
            UNIQUE (run_id, ordinal)
        )
        """
    )
    op.execute("CREATE INDEX ix_research_steps_run ON research_steps (run_id, ordinal)")


def downgrade() -> None:
    op.execute("DROP TABLE research_steps")
    op.execute("DROP TABLE research_runs")
