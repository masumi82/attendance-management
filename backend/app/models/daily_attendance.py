from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DailyAttendanceStatus(str, enum.Enum):
    PENDING = "pending"     # 打刻が揃っていない (clock_in のみ 等)
    NORMAL = "normal"       # 出勤〜退勤 完了
    HOLIDAY = "holiday"     # 休日
    LEAVE = "leave"         # 有給 など（将来 Phase 5）
    ABSENCE = "absence"     # 欠勤
    CLOSED = "closed"       # 月次締め済み (将来 Phase 7)


class DailyAttendance(Base, TimestampMixin):
    __tablename__ = "daily_attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_daily_attendance_employee_date"),
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
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    first_clock_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_clock_out_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    worked_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    break_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    night_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[DailyAttendanceStatus] = mapped_column(
        Enum(
            DailyAttendanceStatus,
            name="daily_attendance_status",
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=DailyAttendanceStatus.PENDING,
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
