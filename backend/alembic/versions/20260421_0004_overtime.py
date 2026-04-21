"""overtime: extend requests CHECK, add overtime_alerts

Revision ID: 0004_overtime
Revises: 0003_requests
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_overtime"
down_revision: str | None = "0003_requests"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Extend requests.type CHECK to include overtime_post
    op.drop_constraint("ck_requests_type", "requests", type_="check")
    op.create_check_constraint(
        "ck_requests_type",
        "requests",
        "type IN ('punch_fix','overtime_pre','overtime_post','leave')",
    )

    op.create_table(
        "overtime_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("year_month", sa.String(length=7), nullable=False),
        sa.Column("threshold_minutes", sa.Integer(), nullable=False),
        sa.Column("overtime_at_send", sa.Integer(), nullable=False),
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
            "employee_id",
            "year_month",
            "threshold_minutes",
            name="uq_overtime_alerts_key",
        ),
    )
    op.create_index(
        "ix_overtime_alerts_employee_id", "overtime_alerts", ["employee_id"]
    )
    op.create_index(
        "ix_overtime_alerts_year_month", "overtime_alerts", ["year_month"]
    )


def downgrade() -> None:
    op.drop_index("ix_overtime_alerts_year_month", table_name="overtime_alerts")
    op.drop_index("ix_overtime_alerts_employee_id", table_name="overtime_alerts")
    op.drop_table("overtime_alerts")

    op.drop_constraint("ck_requests_type", "requests", type_="check")
    op.create_check_constraint(
        "ck_requests_type",
        "requests",
        "type IN ('punch_fix','overtime_pre','leave')",
    )
