from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance

logger = logging.getLogger(__name__)

ANNUAL_PAID = "annual_paid"
# 日本の労基法の簡易モデル（MVP）
# 勤続 6 ヶ月で 10 日付与、+1/年、上限 20 日
BASE_GRANT = Decimal("10")
MAX_GRANT = Decimal("20")


class LeaveError(Exception):
    """Leave balance rule violation."""


@dataclass(slots=True)
class BalanceSummary:
    employee_id: UUID
    employee_name: str
    employee_email: str
    year: int
    leave_type: str
    granted_days: Decimal
    used_days: Decimal
    carried_over_days: Decimal
    remaining_days: Decimal


# ---------------------------------------------------------------------------
# Grant logic
# ---------------------------------------------------------------------------
def _years_of_service(hire_date: date | None, at: date) -> int:
    if hire_date is None:
        return 0
    years = at.year - hire_date.year
    if (at.month, at.day) < (hire_date.month, hire_date.day):
        years -= 1
    return max(0, years)


def compute_annual_grant_days(hire_date: date | None, at: date) -> Decimal:
    """10 days if 6+ months of service, +1 per additional year up to 20."""
    if hire_date is None:
        return Decimal("0")
    delta_months = (at.year - hire_date.year) * 12 + (at.month - hire_date.month)
    if at.day < hire_date.day:
        delta_months -= 1
    if delta_months < 6:
        return Decimal("0")
    years = _years_of_service(hire_date, at)
    return min(BASE_GRANT + Decimal(years), MAX_GRANT)


def grant_annual_leave(
    db: Session, *, employee: Employee, year: int
) -> LeaveBalance:
    """Idempotently grant annual paid leave for the given calendar year."""
    balance = _get_or_create_balance(db, employee.id, year, ANNUAL_PAID)
    at = date(year, 4, 1)  # evaluate grant as of April 1 (fiscal start-ish)
    days = compute_annual_grant_days(employee.hire_date, at)
    balance.granted_days = days
    balance.expires_at = date(year + 2, 3, 31)  # 2 年で失効
    db.flush()
    return balance


def set_granted_days(
    db: Session, *, employee_id, year: int, days: Decimal
) -> LeaveBalance:
    """Directly set the annual paid-leave granted_days for an employee.

    Used for manual overrides when the tenure-based formula would grant 0
    (new hires before 6 months, missing hire_date, etc.).
    """
    balance = _get_or_create_balance(db, employee_id, year, ANNUAL_PAID)
    balance.granted_days = Decimal(days)
    if balance.expires_at is None:
        balance.expires_at = date(year + 2, 3, 31)
    db.flush()
    return balance


def grant_all(db: Session, *, year: int) -> int:
    emps = (
        db.execute(select(Employee).where(Employee.active.is_(True)))
        .scalars()
        .all()
    )
    count = 0
    for emp in emps:
        grant_annual_leave(db, employee=emp, year=year)
        count += 1
    return count


def carry_over(db: Session, *, from_year: int) -> int:
    """Carry remaining days from `from_year` into `from_year+1` as carried_over.

    Idempotent: re-running the same (from_year) sets the target's
    carried_over_days to the current remaining of `from_year` instead of
    adding. Calling twice does not double the carried amount.
    """
    stmt = select(LeaveBalance).where(
        LeaveBalance.year == from_year,
        LeaveBalance.leave_type == ANNUAL_PAID,
    )
    moved = 0
    for prev in db.execute(stmt).scalars().all():
        remaining = (
            prev.granted_days + prev.carried_over_days - prev.used_days
        )
        if remaining <= 0:
            continue
        nxt = _get_or_create_balance(
            db, prev.employee_id, from_year + 1, ANNUAL_PAID
        )
        nxt.carried_over_days = Decimal(remaining)
        moved += 1
    db.flush()
    return moved


# ---------------------------------------------------------------------------
# Deduction on approval
# ---------------------------------------------------------------------------
def count_consumed_days(*, start: date, end: date, leave_kind: str) -> Decimal:
    if leave_kind in ("half_day_am", "half_day_pm"):
        return Decimal("0.5")
    # full_day
    days = (end - start).days + 1
    return Decimal(days)


def deduct_leave(
    db: Session,
    *,
    employee_id: UUID,
    year: int,
    days: Decimal,
    leave_type: str = ANNUAL_PAID,
) -> LeaveBalance:
    balance = _get_or_create_balance(db, employee_id, year, leave_type)
    remaining = (
        balance.granted_days + balance.carried_over_days - balance.used_days
    )
    if remaining < days:
        raise LeaveError(
            f"insufficient_balance: remaining={remaining}, requested={days}"
        )
    balance.used_days = balance.used_days + days
    db.flush()
    return balance


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def _get_or_create_balance(
    db: Session, employee_id: UUID, year: int, leave_type: str
) -> LeaveBalance:
    stmt = select(LeaveBalance).where(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.year == year,
        LeaveBalance.leave_type == leave_type,
    )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        row = LeaveBalance(
            employee_id=employee_id,
            year=year,
            leave_type=leave_type,
            granted_days=Decimal("0"),
            used_days=Decimal("0"),
            carried_over_days=Decimal("0"),
        )
        db.add(row)
        db.flush()
    return row


def get_summary(
    db: Session, *, employee: Employee, year: int, leave_type: str = ANNUAL_PAID
) -> BalanceSummary:
    balance = _get_or_create_balance(db, employee.id, year, leave_type)
    remaining = (
        balance.granted_days + balance.carried_over_days - balance.used_days
    )
    return BalanceSummary(
        employee_id=employee.id,
        employee_name=employee.name,
        employee_email=employee.email,
        year=year,
        leave_type=leave_type,
        granted_days=balance.granted_days,
        used_days=balance.used_days,
        carried_over_days=balance.carried_over_days,
        remaining_days=remaining,
    )


def list_summaries(
    db: Session, *, year: int, leave_type: str = ANNUAL_PAID
) -> list[BalanceSummary]:
    emps = (
        db.execute(
            select(Employee)
            .where(Employee.active.is_(True))
            .order_by(Employee.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [get_summary(db, employee=e, year=year, leave_type=leave_type) for e in emps]


__all__ = [
    "ANNUAL_PAID",
    "BalanceSummary",
    "LeaveError",
    "carry_over",
    "compute_annual_grant_days",
    "count_consumed_days",
    "deduct_leave",
    "get_summary",
    "grant_all",
    "grant_annual_leave",
    "list_summaries",
]
