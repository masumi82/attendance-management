from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MonthlyClosing(Base, TimestampMixin):
    __tablename__ = "monthly_closings"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "year_month", name="uq_monthly_closings_key"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)

    total_worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_overtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_night_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    working_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )
