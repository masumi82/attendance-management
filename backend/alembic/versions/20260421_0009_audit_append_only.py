"""audit_logs: append-only (BEFORE UPDATE/DELETE triggers raise)

Revision ID: 0009_audit_append_only
Revises: 0008_revoked_tokens
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op

revision = "0009_audit_append_only"
down_revision: str | None = "0008_revoked_tokens"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_logs_reject_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only: % is not permitted',
                TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;
        CREATE TRIGGER audit_logs_no_update
        BEFORE UPDATE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_reject_mutation();
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;
        CREATE TRIGGER audit_logs_no_delete
        BEFORE DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION audit_logs_reject_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_update ON audit_logs;")
    op.execute("DROP TRIGGER IF EXISTS audit_logs_no_delete ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_reject_mutation();")
