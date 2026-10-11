"""evidence, claims, claim_basis, claim_evidence: append-only (FR-3.1 to FR-3.3, FR-3.8)

Revision ID: 0011
Revises: 0010
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Verification status is deliberately NOT a column: it is computed from the links (P-05).
    op.execute(
        """
        CREATE TABLE evidence (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            tenant_id text NOT NULL,
            case_id uuid NOT NULL REFERENCES cases (id),
            kind text NOT NULL CHECK (kind IN ('DOCUMENT', 'CONNECTOR', 'WEB')),
            evidence_type text NOT NULL CHECK (evidence_type IN (
                'REGISTRY', 'FINANCIAL', 'LEGAL_REGULATORY', 'NEWS', 'MACRO_INDUSTRY', 'OTHER')),
            source_class text NOT NULL
                CHECK (source_class IN ('OFFICIAL', 'COMMERCIAL', 'SECONDARY', 'WEAK')),
            class_basis text NOT NULL CHECK (class_basis IN ('registry', 'author_declared')),
            source_id uuid REFERENCES sources (id),
            connector_call_id uuid REFERENCES connector_calls (id),
            document_id uuid REFERENCES case_documents (id),
            title text NOT NULL,
            origin text NOT NULL,
            url text,
            published_on date,
            event_on date,
            accessed_at timestamptz NOT NULL,
            excerpt text NOT NULL,
            provenance_ref text,
            content_hash text CHECK (content_hash ~ '^[0-9a-f]{64}$'),
            is_primary boolean NOT NULL,
            discovery_only boolean NOT NULL,
            created_by text NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT evidence_kind_shape CHECK (
                (kind = 'CONNECTOR' AND connector_call_id IS NOT NULL
                    AND provenance_ref IS NOT NULL AND class_basis = 'registry')
                OR (kind = 'DOCUMENT' AND document_id IS NOT NULL)
                OR (kind = 'WEB' AND url IS NOT NULL)
            )
        )
        """
    )
    op.execute("CREATE INDEX ix_evidence_case ON evidence (case_id, seq)")
    op.execute(
        """
        CREATE TABLE claims (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            tenant_id text NOT NULL,
            case_id uuid NOT NULL REFERENCES cases (id),
            text text NOT NULL,
            classification text NOT NULL
                CHECK (classification IN ('FACT', 'INTERPRETATION', 'INFERENCE', 'UNVERIFIED')),
            material boolean NOT NULL,
            adverse boolean NOT NULL,
            credit_relevance text,
            category text CHECK (category IN (
                'ENTITY_REGISTRY', 'FINANCIALS', 'ADVERSE_SEARCH', 'COUNTRY_INDUSTRY', 'OTHER')),
            unavailable_step_id uuid REFERENCES research_steps (id),
            created_by text NOT NULL,
            created_at timestamptz NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ix_claims_case ON claims (case_id, seq)")
    op.execute(
        """
        CREATE TABLE claim_basis (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            claim_id uuid NOT NULL REFERENCES claims (id),
            basis_claim_id uuid NOT NULL REFERENCES claims (id),
            PRIMARY KEY (claim_id, basis_claim_id),
            CHECK (claim_id <> basis_claim_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE claim_evidence (
            seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
            id uuid PRIMARY KEY,
            claim_id uuid NOT NULL REFERENCES claims (id),
            evidence_id uuid NOT NULL REFERENCES evidence (id),
            relation text NOT NULL CHECK (relation IN ('SUPPORTS', 'CONTRADICTS')),
            notes text,
            created_by text NOT NULL,
            created_at timestamptz NOT NULL,
            UNIQUE (claim_id, evidence_id)
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION evidence_tables_block_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER evidence_no_update_delete
        BEFORE UPDATE OR DELETE ON evidence
        FOR EACH ROW EXECUTE FUNCTION evidence_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER evidence_no_truncate
        BEFORE TRUNCATE ON evidence
        FOR EACH STATEMENT EXECUTE FUNCTION evidence_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER claims_no_update_delete
        BEFORE UPDATE OR DELETE ON claims
        FOR EACH ROW EXECUTE FUNCTION evidence_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER claims_no_truncate
        BEFORE TRUNCATE ON claims
        FOR EACH STATEMENT EXECUTE FUNCTION evidence_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER claim_basis_no_update_delete
        BEFORE UPDATE OR DELETE ON claim_basis
        FOR EACH ROW EXECUTE FUNCTION evidence_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER claim_basis_no_truncate
        BEFORE TRUNCATE ON claim_basis
        FOR EACH STATEMENT EXECUTE FUNCTION evidence_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER claim_evidence_no_update_delete
        BEFORE UPDATE OR DELETE ON claim_evidence
        FOR EACH ROW EXECUTE FUNCTION evidence_tables_block_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER claim_evidence_no_truncate
        BEFORE TRUNCATE ON claim_evidence
        FOR EACH STATEMENT EXECUTE FUNCTION evidence_tables_block_change()
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE claim_evidence")
    op.execute("DROP TABLE claim_basis")
    op.execute("DROP TABLE claims")
    op.execute("DROP TABLE evidence")
    op.execute("DROP FUNCTION evidence_tables_block_change()")
