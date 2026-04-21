from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.employee import Employee, Role
from app.schemas.employee import EmployeeCreate, EmployeeUpdate


class EmployeeServiceError(Exception):
    pass


def list_employees(db: Session) -> list[Employee]:
    stmt = select(Employee).order_by(Employee.created_at.asc())
    return list(db.execute(stmt).scalars().all())


def get_employee(db: Session, employee_id: UUID) -> Employee | None:
    return db.get(Employee, employee_id)


def create_employee(db: Session, payload: EmployeeCreate) -> Employee:
    employee = Employee(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        name=payload.name,
        role=payload.role,
        department_id=payload.department_id,
        hire_date=payload.hire_date,
        active=True,
    )
    db.add(employee)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise EmployeeServiceError("email_already_exists") from exc
    return employee


def update_employee(
    db: Session, employee: Employee, payload: EmployeeUpdate
) -> tuple[Employee, dict[str, list]]:
    diff: dict[str, list] = {}
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        raw = data.pop("password")
        if raw:
            employee.hashed_password = hash_password(raw)
            diff["password"] = ["<old>", "<new>"]
    for key, new_value in data.items():
        old = getattr(employee, key)
        if old != new_value:
            diff[key] = [_serialize(old), _serialize(new_value)]
            setattr(employee, key, new_value)
    db.flush()
    return employee, diff


def _serialize(value):
    if isinstance(value, Role):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)
