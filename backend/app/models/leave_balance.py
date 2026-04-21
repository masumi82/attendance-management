from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class LeaveBalance(Base, TimestampMixin):
    __tablename__ = "leave_balances"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "year",
            "leave_type",
            name="uq_leave_balances_key",
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
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    leave_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="annual_paid"
    )
    granted_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False, default=Decimal("0")
    )
    used_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False, default=Decimal("0")
    )
    carried_over_days: Mapped[Decimal] = mapped_column(
        Numeric(5, 1), nullable=False, default=Decimal("0")
    )
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
