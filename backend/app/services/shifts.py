from __future__ import annotations

from datetime import date, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.employment_type import EmploymentType
from app.models.shift import Shift


class ShiftError(Exception):
    pass


def upsert_shift(
    db: Session,
    *,
    employee_id: UUID,
    work_date: date,
    start_time: time,
    end_time: time,
    break_minutes: int = 60,
) -> Shift:
    if end_time <= start_time:
        raise ShiftError("end_before_start")
    stmt = select(Shift).where(
        Shift.employee_id == employee_id, Shift.work_date == work_date
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is None:
        existing = Shift(
            employee_id=employee_id,
            work_date=work_date,
            start_time=start_time,
            end_time=end_time,
            break_minutes=break_minutes,
        )
        db.add(existing)
    else:
        existing.start_time = start_time
        existing.end_time = end_time
        existing.break_minutes = break_minutes
    db.flush()
    return existing


def delete_shift(db: Session, *, shift_id: UUID) -> bool:
    shift = db.get(Shift, shift_id)
    if shift is None:
        return False
    db.delete(shift)
    db.flush()
    return True


def list_shifts_month(
    db: Session, *, employee_id: UUID, year: int, month: int
) -> list[Shift]:
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    stmt = (
        select(Shift)
        .where(
            Shift.employee_id == employee_id,
            Shift.work_date >= start,
            Shift.work_date < end,
        )
        .order_by(Shift.work_date.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_employment_type(db: Session, *, code: str) -> EmploymentType | None:
    stmt = select(EmploymentType).where(EmploymentType.code == code)
    return db.execute(stmt).scalar_one_or_none()


def list_employment_types(db: Session) -> list[EmploymentType]:
    return list(db.execute(select(EmploymentType).order_by(EmploymentType.code.asc())).scalars().all())


def assign_employment_type(
    db: Session, *, employee: Employee, employment_type_id: UUID | None
) -> Employee:
    employee.employment_type_id = employment_type_id
    db.flush()
    return employee
