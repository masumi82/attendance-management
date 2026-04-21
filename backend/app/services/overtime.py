from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.daily_attendance import DailyAttendance
from app.models.employee import Employee, Role
from app.models.overtime_alert import OvertimeAlert
from app.services.notifier import broadcast

logger = logging.getLogger(__name__)

# 36 協定の目安閾値（分）
THRESHOLDS_MINUTES: list[int] = [45 * 60, 80 * 60, 100 * 60]


@dataclass(slots=True)
class OvertimeRow:
    employee_id: UUID
    employee_name: str
    employee_email: str
    total_overtime_minutes: int
    total_worked_minutes: int
    working_days: int
    alerts_sent: list[int]  # thresholds (minutes) already notified


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    return start, end


def _year_month_str(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def compute_monthly_overtime(
    db: Session, *, employee_id: UUID, year: int, month: int
) -> tuple[int, int, int]:
    """Return (total_overtime_min, total_worked_min, working_days)."""
    start, end = _month_range(year, month)
    stmt = select(
        func.coalesce(func.sum(DailyAttendance.overtime_minutes), 0),
        func.coalesce(func.sum(DailyAttendance.worked_minutes), 0),
        func.count(DailyAttendance.id).filter(DailyAttendance.worked_minutes > 0),
    ).where(
        DailyAttendance.employee_id == employee_id,
        DailyAttendance.work_date >= start,
        DailyAttendance.work_date < end,
    )
    row = db.execute(stmt).one()
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)


def list_monthly_overtime(
    db: Session, *, year: int, month: int
) -> list[OvertimeRow]:
    ym = _year_month_str(year, month)
    employees = (
        db.execute(
            select(Employee)
            .where(Employee.active.is_(True))
            .order_by(Employee.created_at.asc())
        )
        .scalars()
        .all()
    )
    alerts_map: dict[UUID, list[int]] = {}
    alerts = (
        db.execute(
            select(OvertimeAlert).where(OvertimeAlert.year_month == ym)
        )
        .scalars()
        .all()
    )
    for a in alerts:
        alerts_map.setdefault(a.employee_id, []).append(a.threshold_minutes)

    rows: list[OvertimeRow] = []
    for emp in employees:
        ot, worked, days = compute_monthly_overtime(
            db, employee_id=emp.id, year=year, month=month
        )
        rows.append(
            OvertimeRow(
                employee_id=emp.id,
                employee_name=emp.name,
                employee_email=emp.email,
                total_overtime_minutes=ot,
                total_worked_minutes=worked,
                working_days=days,
                alerts_sent=sorted(alerts_map.get(emp.id, [])),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Alert checks
# ---------------------------------------------------------------------------
def check_and_alert_overtime(
    db: Session, *, employee: Employee, year: int, month: int
) -> list[int]:
    """Send alerts for newly-crossed thresholds. Returns list of thresholds sent."""
    ym = _year_month_str(year, month)
    total_ot, _, _ = compute_monthly_overtime(
        db, employee_id=employee.id, year=year, month=month
    )

    already_sent = set(
        db.execute(
            select(OvertimeAlert.threshold_minutes).where(
                OvertimeAlert.employee_id == employee.id,
                OvertimeAlert.year_month == ym,
            )
        )
        .scalars()
        .all()
    )

    sent: list[int] = []
    for threshold in THRESHOLDS_MINUTES:
        if total_ot < threshold or threshold in already_sent:
            continue
        # Use a SAVEPOINT so a unique-violation (race) only rolls back the
        # OvertimeAlert insert, not the caller's uncommitted work.
        savepoint = db.begin_nested()
        record = OvertimeAlert(
            employee_id=employee.id,
            year_month=ym,
            threshold_minutes=threshold,
            overtime_at_send=total_ot,
        )
        db.add(record)
        try:
            db.flush()
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
            continue
        _notify(db, employee=employee, year_month=ym, threshold=threshold, total_ot=total_ot)
        sent.append(threshold)
    return sent


def _notify(
    db: Session,
    *,
    employee: Employee,
    year_month: str,
    threshold: int,
    total_ot: int,
) -> None:
    # Gather approver/admin emails
    staff_emails = list(
        db.execute(
            select(Employee.email).where(
                Employee.active.is_(True),
                Employee.role.in_([Role.ADMIN, Role.APPROVER]),
            )
        )
        .scalars()
        .all()
    )
    recipients = list({employee.email, *staff_emails})
    threshold_hr = threshold // 60
    total_hr = total_ot // 60
    total_min = total_ot % 60
    broadcast(
        recipients,
        subject=f"[勤怠管理] 残業 {threshold_hr}h 超過の通知: {employee.name} ({year_month})",
        body=(
            f"対象者: {employee.name} <{employee.email}>\n"
            f"対象月: {year_month}\n"
            f"現在の月次残業合計: {total_hr}時間{total_min:02d}分\n"
            f"超過した閾値: {threshold_hr}時間\n"
        ),
    )


def run_all_employees_check(db: Session, *, year: int, month: int) -> int:
    """Scheduled entry point. Returns number of alerts sent across employees."""
    emps = (
        db.execute(
            select(Employee).where(Employee.active.is_(True))
        )
        .scalars()
        .all()
    )
    total = 0
    for emp in emps:
        sent = check_and_alert_overtime(db, employee=emp, year=year, month=month)
        total += len(sent)
    if total:
        logger.info("overtime: sent %d new alerts (ym=%d-%02d)", total, year, month)
    return total


__all__ = [
    "OvertimeRow",
    "THRESHOLDS_MINUTES",
    "check_and_alert_overtime",
    "compute_monthly_overtime",
    "list_monthly_overtime",
    "run_all_employees_check",
]
