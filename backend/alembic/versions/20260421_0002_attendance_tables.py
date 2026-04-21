"""attendance tables: attendance_punches, daily_attendance

Revision ID: 0002_attendance
Revises: 0001_initial_auth
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_attendance"
down_revision: str | None = "0001_initial_auth"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "attendance_punches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("punched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column(
            "source", sa.String(length=16), nullable=False, server_default="web"
        ),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
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
    op.create_index(
        "ix_attendance_punches_employee_date",
        "attendance_punches",
        ["employee_id", "work_date"],
    )
    op.create_index(
        "ix_attendance_punches_punched_at",
        "attendance_punches",
        ["punched_at"],
    )
    op.create_check_constraint(
        "ck_attendance_punch_type",
        "attendance_punches",
        "type IN ('clock_in','clock_out','break_start','break_end')",
    )
    op.create_check_constraint(
        "ck_attendance_punch_source",
        "attendance_punches",
        "source IN ('web','admin')",
    )

    op.create_table(
        "daily_attendance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("first_clock_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_clock_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "worked_minutes", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "break_minutes", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "overtime_minutes", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "night_minutes", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
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
            "employee_id", "work_date", name="uq_daily_attendance_employee_date"
        ),
    )
    op.create_index(
        "ix_daily_attendance_employee_id",
        "daily_attendance",
        ["employee_id"],
    )
    op.create_index(
        "ix_daily_attendance_work_date", "daily_attendance", ["work_date"]
    )
    op.create_check_constraint(
        "ck_daily_attendance_status",
        "daily_attendance",
        "status IN ('pending','normal','holiday','leave','absence','closed')",
    )


def downgrade() -> None:
    op.drop_index("ix_daily_attendance_work_date", table_name="daily_attendance")
    op.drop_index("ix_daily_attendance_employee_id", table_name="daily_attendance")
    op.drop_constraint(
        "ck_daily_attendance_status", "daily_attendance", type_="check"
    )
    op.drop_table("daily_attendance")

    op.drop_constraint(
        "ck_attendance_punch_source", "attendance_punches", type_="check"
    )
    op.drop_constraint(
        "ck_attendance_punch_type", "attendance_punches", type_="check"
    )
    op.drop_index("ix_attendance_punches_punched_at", table_name="attendance_punches")
    op.drop_index(
        "ix_attendance_punches_employee_date", table_name="attendance_punches"
    )
    op.drop_table("attendance_punches")
