"""holidays and monthly_closings

Revision ID: 0007_closings
Revises: 0006_shifts
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_closings"
down_revision: str | None = "0006_shifts"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "holidays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "type", sa.String(length=16), nullable=False, server_default="national"
        ),
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
    )
    op.create_check_constraint(
        "ck_holidays_type", "holidays", "type IN ('national','company')"
    )

    op.create_table(
        "monthly_closings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column(
            "total_worked_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_overtime_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_night_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "total_break_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "working_days", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "closed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
            "employee_id", "year_month", name="uq_monthly_closings_key"
        ),
    )
    op.create_index(
        "ix_monthly_closings_employee_id",
        "monthly_closings",
        ["employee_id"],
    )
    op.create_index(
        "ix_monthly_closings_year_month",
        "monthly_closings",
        ["year_month"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_monthly_closings_year_month", table_name="monthly_closings"
    )
    op.drop_index(
        "ix_monthly_closings_employee_id", table_name="monthly_closings"
    )
    op.drop_table("monthly_closings")

    op.drop_constraint("ck_holidays_type", "holidays", type_="check")
    op.drop_table("holidays")
