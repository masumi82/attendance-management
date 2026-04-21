"""leave_balances table

Revision ID: 0005_leave_balances
Revises: 0004_overtime
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_leave_balances"
down_revision: str | None = "0004_overtime"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "leave_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column(
            "leave_type",
            sa.String(length=32),
            nullable=False,
            server_default="annual_paid",
        ),
        sa.Column(
            "granted_days", sa.Numeric(5, 1), nullable=False, server_default="0"
        ),
        sa.Column(
            "used_days", sa.Numeric(5, 1), nullable=False, server_default="0"
        ),
        sa.Column(
            "carried_over_days",
            sa.Numeric(5, 1),
            nullable=False,
            server_default="0",
        ),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "employee_id", "year", "leave_type", name="uq_leave_balances_key"
        ),
    )
    op.create_index(
        "ix_leave_balances_employee_id", "leave_balances", ["employee_id"]
    )
    op.create_index("ix_leave_balances_year", "leave_balances", ["year"])


def downgrade() -> None:
    op.drop_index("ix_leave_balances_year", table_name="leave_balances")
    op.drop_index("ix_leave_balances_employee_id", table_name="leave_balances")
    op.drop_table("leave_balances")
