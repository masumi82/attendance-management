from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.attendance_punch import PunchType
from app.models.daily_attendance import DailyAttendanceStatus


class PunchRequest(BaseModel):
    type: PunchType = Field(description="打刻種別")


class PunchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    work_date: date
    punched_at: datetime
    type: PunchType
    source: str


class DailyAttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    work_date: date
    first_clock_in_at: datetime | None
    last_clock_out_at: datetime | None
    worked_minutes: int
    break_minutes: int
    overtime_minutes: int
    night_minutes: int
    status: DailyAttendanceStatus


class TodayResponse(BaseModel):
    work_date: date
    state: str  # 'none' | 'working' | 'on_break' | 'done'
    punches: list[PunchOut]
    daily: DailyAttendanceOut | None


class MonthlyStats(BaseModel):
    working_days: int
    total_worked_minutes: int
    total_overtime_minutes: int
    total_night_minutes: int
    total_break_minutes: int


class MonthlyResponse(BaseModel):
    year: int
    month: int
    days: list[DailyAttendanceOut]
    stats: MonthlyStats
