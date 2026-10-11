"""sources: the source and connector capability registry (FR-2.1, FR-2.2)

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No credential column on purpose: secrets live in a secrets store, never in this table.
    op.execute(
        """
        CREATE TABLE sources (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            tenant_id text NOT NULL,
            key text NOT NULL CHECK (key ~ '^[a-z0-9][a-z0-9_-]{1,59}$'),
            name text NOT NULL,
            source_class text NOT NULL
                CHECK (source_class IN ('OFFICIAL', 'COMMERCIAL', 'SECONDARY', 'WEAK')),
            source_type text NOT NULL,
            jurisdictions text[] NOT NULL CHECK (cardinality(jurisdictions) >= 1),
            access_category text NOT NULL CHECK (access_category IN (
                'ACTUALLY_ACCESSIBLE', 'RESTRICTED_LICENSED', 'DISCOVERY_ONLY',
                'TECHNICALLY_UNAVAILABLE')),
            auth_state text NOT NULL
                CHECK (auth_state IN ('NOT_REQUIRED', 'CONFIGURED', 'MISSING')),
            terms_notes text,
            rate_limit_per_minute integer CHECK (rate_limit_per_minute > 0),
            health text NOT NULL DEFAULT 'UNKNOWN'
                CHECK (health IN ('UNKNOWN', 'HEALTHY', 'DEGRADED', 'DOWN')),
            health_checked_at timestamptz,
            version integer NOT NULL CHECK (version >= 1),
            created_by text NOT NULL,
            created_at timestamptz NOT NULL,
            updated_at timestamptz NOT NULL,
            UNIQUE (tenant_id, key),
            -- A source that needs a credential we do not hold cannot be reported as accessible.
            CONSTRAINT source_accessible_needs_auth CHECK (
                access_category <> 'ACTUALLY_ACCESSIBLE' OR auth_state <> 'MISSING'
            )
        )
        """
    )
    op.execute("CREATE INDEX ix_sources_tenant ON sources (tenant_id, seq)")


def downgrade() -> None:
    op.execute("DROP TABLE sources")
