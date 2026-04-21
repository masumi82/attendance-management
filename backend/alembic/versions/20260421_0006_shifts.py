"""employment_types, shifts, employees.employment_type_id

Revision ID: 0006_shifts
Revises: 0005_leave_balances
Create Date: 2026-04-21
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_shifts"
down_revision: str | None = "0005_leave_balances"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "employment_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "standard_daily_minutes",
            sa.Integer(),
            nullable=False,
            server_default="480",
        ),
        sa.Column(
            "standard_weekly_minutes",
            sa.Integer(),
            nullable=False,
            server_default="2400",
        ),
        sa.Column("core_start", sa.Time(), nullable=True),
        sa.Column("core_end", sa.Time(), nullable=True),
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

    # Seed defaults
    employment_types = sa.table(
        "employment_types",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("standard_daily_minutes", sa.Integer),
        sa.column("standard_weekly_minutes", sa.Integer),
        sa.column("core_start", sa.Time),
        sa.column("core_end", sa.Time),
    )
    op.bulk_insert(
        employment_types,
        [
            {
                "id": uuid.uuid4(),
                "code": "standard",
                "name": "通常勤務",
                "standard_daily_minutes": 480,
                "standard_weekly_minutes": 2400,
                "core_start": None,
                "core_end": None,
            },
            {
                "id": uuid.uuid4(),
                "code": "shift",
                "name": "シフト勤務",
                "standard_daily_minutes": 480,
                "standard_weekly_minutes": 2400,
                "core_start": None,
                "core_end": None,
            },
            {
                "id": uuid.uuid4(),
                "code": "flex",
                "name": "フレックスタイム",
                "standard_daily_minutes": 480,
                "standard_weekly_minutes": 2400,
                "core_start": __import__("datetime").time(10, 0),
                "core_end": __import__("datetime").time(15, 0),
            },
        ],
    )

    op.add_column(
        "employees",
        sa.Column(
            "employment_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employment_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "shifts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column(
            "break_minutes", sa.Integer(), nullable=False, server_default="60"
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
            "employee_id", "work_date", name="uq_shifts_employee_date"
        ),
    )
    op.create_index("ix_shifts_employee_id", "shifts", ["employee_id"])
    op.create_index("ix_shifts_work_date", "shifts", ["work_date"])


def downgrade() -> None:
    op.drop_index("ix_shifts_work_date", table_name="shifts")
    op.drop_index("ix_shifts_employee_id", table_name="shifts")
    op.drop_table("shifts")

    op.drop_column("employees", "employment_type_id")
    op.drop_table("employment_types")
