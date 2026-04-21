"""revoked_access_tokens

Revision ID: 0008_revoked_tokens
Revises: 0007_closings
Create Date: 2026-04-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_revoked_tokens"
down_revision: str | None = "0007_closings"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "revoked_access_tokens",
        sa.Column("jti", sa.String(length=64), primary_key=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False, server_default="logout"),
    )
    op.create_index(
        "ix_revoked_access_tokens_expires_at",
        "revoked_access_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_revoked_access_tokens_expires_at",
        table_name="revoked_access_tokens",
    )
    op.drop_table("revoked_access_tokens")
