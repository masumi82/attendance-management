from __future__ import annotations

import uuid

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class OvertimeAlert(Base, TimestampMixin):
    """One row per (employee, year_month, threshold) to dedupe alerts."""

    __tablename__ = "overtime_alerts"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "year_month",
            "threshold_minutes",
            name="uq_overtime_alerts_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False, index=True
    )
    year_month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    threshold_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    overtime_at_send: Mapped[int] = mapped_column(Integer, nullable=False)
