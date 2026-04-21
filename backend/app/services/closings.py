from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attendance_punch import AttendancePunch
from app.models.daily_attendance import DailyAttendance
from app.models.employee import Employee
from app.models.monthly_closing import MonthlyClosing
from app.services import attendance as attendance_service

JST = ZoneInfo("Asia/Tokyo")


class ClosingError(Exception):
    pass


def year_month_str(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    return start, end


def is_month_closed_for(
    db: Session, *, employee_id: UUID, year: int, month: int
) -> bool:
    ym = year_month_str(year, month)
    stmt = select(MonthlyClosing).where(
        MonthlyClosing.employee_id == employee_id,
        MonthlyClosing.year_month == ym,
        MonthlyClosing.closed_at.isnot(None),
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def get_closing(
    db: Session, *, employee_id: UUID, year: int, month: int
) -> MonthlyClosing | None:
    ym = year_month_str(year, month)
    stmt = select(MonthlyClosing).where(
        MonthlyClosing.employee_id == employee_id,
        MonthlyClosing.year_month == ym,
    )
    return db.execute(stmt).scalar_one_or_none()


def list_status(
    db: Session, *, year: int, month: int
) -> list[tuple[Employee, MonthlyClosing | None]]:
    employees = (
        db.execute(
            select(Employee).where(Employee.active.is_(True)).order_by(Employee.created_at.asc())
        )
        .scalars()
        .all()
    )
    result: list[tuple[Employee, MonthlyClosing | None]] = []
    for emp in employees:
        result.append((emp, get_closing(db, employee_id=emp.id, year=year, month=month)))
    return result


def recompute_month(
    db: Session, *, employee_id: UUID, year: int, month: int
) -> dict:
    """Recompute every daily_attendance in the month from its punches."""
    start, end = _month_range(year, month)
    # Collect distinct dates that have punches
    dates = (
        db.execute(
            select(AttendancePunch.work_date)
            .where(
                AttendancePunch.employee_id == employee_id,
                AttendancePunch.work_date >= start,
                AttendancePunch.work_date < end,
            )
            .distinct()
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for d in dates:
        attendance_service.recompute_daily(
            db, employee_id=employee_id, work_date=d, now=now
        )

    totals = _sum_month(db, employee_id=employee_id, year=year, month=month)
    ym = year_month_str(year, month)
    closing = get_closing(db, employee_id=employee_id, year=year, month=month)
    if closing is None:
        closing = MonthlyClosing(employee_id=employee_id, year_month=ym)
        db.add(closing)
    closing.total_worked_minutes = totals["worked"]
    closing.total_overtime_minutes = totals["overtime"]
    closing.total_night_minutes = totals["night"]
    closing.total_break_minutes = totals["break_"]
    closing.working_days = totals["days"]
    db.flush()
    return totals


def close_month(
    db: Session,
    *,
    employee_id: UUID,
    year: int,
    month: int,
    actor_id: UUID | None,
) -> MonthlyClosing:
    totals = recompute_month(db, employee_id=employee_id, year=year, month=month)
    closing = get_closing(db, employee_id=employee_id, year=year, month=month)
    assert closing is not None
    if closing.closed_at is not None:
        raise ClosingError("already_closed")
    closing.closed_at = datetime.now(UTC)
    closing.closed_by_id = actor_id
    # ensure totals are in the closing
    closing.total_worked_minutes = totals["worked"]
    closing.total_overtime_minutes = totals["overtime"]
    closing.total_night_minutes = totals["night"]
    closing.total_break_minutes = totals["break_"]
    closing.working_days = totals["days"]
    db.flush()
    return closing


def reopen_month(
    db: Session, *, employee_id: UUID, year: int, month: int
) -> MonthlyClosing:
    closing = get_closing(db, employee_id=employee_id, year=year, month=month)
    if closing is None or closing.closed_at is None:
        raise ClosingError("not_closed")
    closing.closed_at = None
    closing.closed_by_id = None
    db.flush()
    return closing


def close_all(
    db: Session, *, year: int, month: int, actor_id: UUID | None
) -> int:
    employees = (
        db.execute(
            select(Employee).where(Employee.active.is_(True))
        )
        .scalars()
        .all()
    )
    n = 0
    for emp in employees:
        closing = get_closing(db, employee_id=emp.id, year=year, month=month)
        if closing is not None and closing.closed_at is not None:
            continue
        close_month(db, employee_id=emp.id, year=year, month=month, actor_id=actor_id)
        n += 1
    return n


def _sum_month(
    db: Session, *, employee_id: UUID, year: int, month: int
) -> dict:
    start, end = _month_range(year, month)
    row = db.execute(
        select(
            func.coalesce(func.sum(DailyAttendance.worked_minutes), 0),
            func.coalesce(func.sum(DailyAttendance.overtime_minutes), 0),
            func.coalesce(func.sum(DailyAttendance.night_minutes), 0),
            func.coalesce(func.sum(DailyAttendance.break_minutes), 0),
            func.count().filter(DailyAttendance.worked_minutes > 0),
        ).where(
            DailyAttendance.employee_id == employee_id,
            DailyAttendance.work_date >= start,
            DailyAttendance.work_date < end,
        )
    ).one()
    return {
        "worked": int(row[0] or 0),
        "overtime": int(row[1] or 0),
        "night": int(row[2] or 0),
        "break_": int(row[3] or 0),
        "days": int(row[4] or 0),
    }


__all__ = [
    "ClosingError",
    "close_all",
    "close_month",
    "get_closing",
    "is_month_closed_for",
    "list_status",
    "recompute_month",
    "reopen_month",
    "year_month_str",
]
