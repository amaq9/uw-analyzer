"""entity unconfirmed: a person can record that the legal entity could not be confirmed or found

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE cases DROP CONSTRAINT cases_status_check")
    op.execute(
        "ALTER TABLE cases ADD CONSTRAINT cases_status_check CHECK (status IN "
        "('DRAFT', 'ENTITY_AMBIGUOUS', 'ENTITY_RESOLVED', 'ENTITY_UNCONFIRMED'))"
    )
    op.execute(
        "ALTER TABLE entity_resolution_log DROP CONSTRAINT entity_resolution_log_action_check"
    )
    op.execute(
        "ALTER TABLE entity_resolution_log ADD CONSTRAINT entity_resolution_log_action_check "
        "CHECK (action IN ('resolved', 'reopened', 'unconfirmed'))"
    )


def downgrade() -> None:
    op.execute("UPDATE cases SET status = 'DRAFT' WHERE status = 'ENTITY_UNCONFIRMED'")
    op.execute("ALTER TABLE cases DROP CONSTRAINT cases_status_check")
    op.execute(
        "ALTER TABLE cases ADD CONSTRAINT cases_status_check CHECK (status IN "
        "('DRAFT', 'ENTITY_AMBIGUOUS', 'ENTITY_RESOLVED'))"
    )
    # The resolution log is append-only, so existing 'unconfirmed' entries are history that must not
    # be rewritten. NOT VALID restores the old rule for new rows without re-checking old ones.
    op.execute(
        "ALTER TABLE entity_resolution_log DROP CONSTRAINT entity_resolution_log_action_check"
    )
    op.execute(
        "ALTER TABLE entity_resolution_log ADD CONSTRAINT entity_resolution_log_action_check "
        "CHECK (action IN ('resolved', 'reopened')) NOT VALID"
    )
