from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attendance_punch import AttendancePunch, PunchType
from app.models.daily_attendance import DailyAttendance
from app.models.employee import Employee
from app.models.employment_type import EmploymentType

JST = ZoneInfo("Asia/Tokyo")


@dataclass(slots=True)
class FlexSettlement:
    employee_id: UUID
    year: int
    month: int
    employment_type_code: str | None
    required_minutes: int  # 所定労働 (working_days * standard_daily_minutes)
    worked_minutes: int
    surplus_minutes: int  # actual - required (negative if deficit)
    core_start: time | None
    core_end: time | None
    core_violation_dates: list[date]
    working_days: int


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    return start, end


def _business_days(start: date, end_exclusive: date) -> int:
    days = 0
    cur = start
    while cur < end_exclusive:
        if cur.weekday() < 5:  # Mon-Fri
            days += 1
        cur = cur + timedelta(days=1)
    return days


def compute_flex_settlement(
    db: Session, *, employee: Employee, year: int, month: int
) -> FlexSettlement:
    start, end = _month_range(year, month)

    etype: EmploymentType | None = None
    if employee.employment_type_id is not None:
        etype = db.get(EmploymentType, employee.employment_type_id)

    daily_minutes = etype.standard_daily_minutes if etype else 480
    required = _business_days(start, end) * daily_minutes

    worked_sum = int(
        db.execute(
            select(
                func.coalesce(func.sum(DailyAttendance.worked_minutes), 0)
            ).where(
                DailyAttendance.employee_id == employee.id,
                DailyAttendance.work_date >= start,
                DailyAttendance.work_date < end,
            )
        ).scalar_one()
    )
    working_days = int(
        db.execute(
            select(func.count())
            .select_from(DailyAttendance)
            .where(
                DailyAttendance.employee_id == employee.id,
                DailyAttendance.work_date >= start,
                DailyAttendance.work_date < end,
                DailyAttendance.worked_minutes > 0,
            )
        ).scalar_one()
    )

    violations: list[date] = []
    core_start = etype.core_start if etype else None
    core_end = etype.core_end if etype else None

    if core_start and core_end:
        violations = _core_time_violations(
            db,
            employee_id=employee.id,
            start=start,
            end=end,
            core_start=core_start,
            core_end=core_end,
        )

    return FlexSettlement(
        employee_id=employee.id,
        year=year,
        month=month,
        employment_type_code=etype.code if etype else None,
        required_minutes=required,
        worked_minutes=worked_sum,
        surplus_minutes=worked_sum - required,
        core_start=core_start,
        core_end=core_end,
        core_violation_dates=violations,
        working_days=working_days,
    )


def _core_time_violations(
    db: Session,
    *,
    employee_id: UUID,
    start: date,
    end: date,
    core_start: time,
    core_end: time,
) -> list[date]:
    """Days where the employee worked but NOT fully covering [core_start, core_end]."""
    stmt = (
        select(AttendancePunch)
        .where(
            AttendancePunch.employee_id == employee_id,
            AttendancePunch.work_date >= start,
            AttendancePunch.work_date < end,
        )
        .order_by(AttendancePunch.work_date.asc(), AttendancePunch.punched_at.asc())
    )
    punches = list(db.execute(stmt).scalars().all())
    if not punches:
        return []

    by_day: dict[date, list[AttendancePunch]] = {}
    for p in punches:
        by_day.setdefault(p.work_date, []).append(p)

    violations: list[date] = []
    for day, ps in by_day.items():
        clock_in = next((p for p in ps if p.type == PunchType.CLOCK_IN), None)
        clock_out = next(
            (p for p in reversed(ps) if p.type == PunchType.CLOCK_OUT), None
        )
        if clock_in is None:
            continue
        start_jst = clock_in.punched_at.astimezone(JST)
        end_jst = (
            clock_out.punched_at.astimezone(JST)
            if clock_out
            else datetime.now(UTC).astimezone(JST)
        )
        core_start_dt = datetime.combine(day, core_start, tzinfo=JST)
        core_end_dt = datetime.combine(day, core_end, tzinfo=JST)

        # Violates if first clock-in is after core_start OR last clock-out is before core_end
        if start_jst > core_start_dt or end_jst < core_end_dt:
            violations.append(day)
    return violations


__all__ = [
    "FlexSettlement",
    "compute_flex_settlement",
]
