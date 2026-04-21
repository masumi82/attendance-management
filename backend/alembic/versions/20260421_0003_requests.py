"""requests and approvals tables

Revision ID: 0003_requests
Revises: 0002_attendance
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_requests"
down_revision: str | None = "0002_attendance"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=24), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("requester_comment", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
    op.create_index("ix_requests_employee_id", "requests", ["employee_id"])
    op.create_index("ix_requests_status", "requests", ["status"])
    op.create_index("ix_requests_target_date", "requests", ["target_date"])
    op.create_check_constraint(
        "ck_requests_type",
        "requests",
        "type IN ('punch_fix','overtime_pre','leave')",
    )
    op.create_check_constraint(
        "ck_requests_status",
        "requests",
        "status IN ('draft','pending','approved','rejected','canceled')",
    )

    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "approver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "decision",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
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
    op.create_index("ix_approvals_request_id", "approvals", ["request_id"])
    op.create_check_constraint(
        "ck_approvals_decision",
        "approvals",
        "decision IN ('pending','approved','rejected')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_approvals_decision", "approvals", type_="check")
    op.drop_index("ix_approvals_request_id", table_name="approvals")
    op.drop_table("approvals")

    op.drop_constraint("ck_requests_status", "requests", type_="check")
    op.drop_constraint("ck_requests_type", "requests", type_="check")
    op.drop_index("ix_requests_target_date", table_name="requests")
    op.drop_index("ix_requests_status", table_name="requests")
    op.drop_index("ix_requests_employee_id", table_name="requests")
    op.drop_table("requests")
