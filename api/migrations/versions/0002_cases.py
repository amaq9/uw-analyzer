"""cases: Phase 1 intake table (FR-1.1)

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE cases (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            tenant_id text NOT NULL,
            owner text NOT NULL,
            status text NOT NULL DEFAULT 'DRAFT'
                CHECK (status IN ('DRAFT', 'ENTITY_AMBIGUOUS', 'ENTITY_RESOLVED')),
            legal_name text,
            trading_name text,
            registration_number text,
            jurisdiction text,
            address text,
            website text,
            industry text,
            parent_name text,
            ubo_name text,
            exposure_amount numeric(18, 2) CHECK (exposure_amount >= 0),
            exposure_currency text CHECK (exposure_currency ~ '^[A-Z]{3}$'),
            terms text,
            context text,
            version integer NOT NULL DEFAULT 1,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            CONSTRAINT cases_has_name CHECK (legal_name IS NOT NULL OR trading_name IS NOT NULL),
            CONSTRAINT cases_exposure_pair
                CHECK ((exposure_amount IS NULL) = (exposure_currency IS NULL))
        )
        """
    )
    op.execute("CREATE INDEX ix_cases_tenant_created ON cases (tenant_id, seq DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE cases")
