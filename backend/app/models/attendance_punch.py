from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PunchType(str, enum.Enum):
    CLOCK_IN = "clock_in"
    CLOCK_OUT = "clock_out"
    BREAK_START = "break_start"
    BREAK_END = "break_end"


class PunchSource(str, enum.Enum):
    WEB = "web"
    ADMIN = "admin"


class AttendancePunch(Base, TimestampMixin):
    """Append-only raw punch event."""

    __tablename__ = "attendance_punches"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    punched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    type: Mapped[PunchType] = mapped_column(
        Enum(
            PunchType,
            name="punch_type",
            native_enum=False,
            length=20,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    source: Mapped[PunchSource] = mapped_column(
        Enum(
            PunchSource,
            name="punch_source",
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=PunchSource.WEB,
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
