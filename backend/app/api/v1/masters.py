from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.department import Department
from app.models.employee import Employee
from app.models.holiday import Holiday
from app.schemas.masters import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    HolidayCreate,
    HolidayOut,
)

router = APIRouter(prefix="/v1/departments", tags=["departments"])
admin_dept_router = APIRouter(
    prefix="/v1/admin/departments", tags=["admin", "departments"]
)
holidays_router = APIRouter(prefix="/v1/holidays", tags=["holidays"])
admin_holidays_router = APIRouter(
    prefix="/v1/admin/holidays", tags=["admin", "holidays"]
)


# ---------- Departments ----------
@router.get("", response_model=list[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db),
    _current: Employee = Depends(get_current_user),
) -> list[DepartmentOut]:
    rows = db.execute(select(Department).order_by(Department.name.asc())).scalars().all()
    return [DepartmentOut.model_validate(r) for r in rows]


@admin_dept_router.post("", response_model=DepartmentOut, status_code=201)
def create_department(
    body: DepartmentCreate,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> DepartmentOut:
    dept = Department(name=body.name, code=body.code)
    db.add(dept)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="duplicate") from None
    db.refresh(dept)
    return DepartmentOut.model_validate(dept)


@admin_dept_router.patch("/{dept_id}", response_model=DepartmentOut)
def update_department(
    dept_id: UUID,
    body: DepartmentUpdate,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> DepartmentOut:
    dept = db.get(Department, dept_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="not_found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(dept, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="duplicate") from None
    db.refresh(dept)
    return DepartmentOut.model_validate(dept)


@admin_dept_router.delete("/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    dept_id: UUID,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> None:
    dept = db.get(Department, dept_id)
    if dept is None:
        raise HTTPException(status_code=404, detail="not_found")
    db.delete(dept)
    db.commit()


# ---------- Holidays ----------
@holidays_router.get("", response_model=list[HolidayOut])
def list_holidays(
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    _current: Employee = Depends(get_current_user),
) -> list[HolidayOut]:
    stmt = select(Holiday).order_by(Holiday.date.asc())
    if year is not None:
        from datetime import date as date_

        start = date_(year, 1, 1)
        end = date_(year + 1, 1, 1)
        stmt = stmt.where(Holiday.date >= start, Holiday.date < end)
    rows = db.execute(stmt).scalars().all()
    return [HolidayOut.model_validate(r) for r in rows]


@admin_holidays_router.post("", response_model=HolidayOut, status_code=201)
def create_holiday(
    body: HolidayCreate,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> HolidayOut:
    h = Holiday(date=body.date, name=body.name, type=body.type)
    db.add(h)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="duplicate_date") from None
    db.refresh(h)
    return HolidayOut.model_validate(h)


@admin_holidays_router.delete(
    "/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_holiday(
    holiday_id: UUID,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> None:
    h = db.get(Holiday, holiday_id)
    if h is None:
        raise HTTPException(status_code=404, detail="not_found")
    db.delete(h)
    db.commit()
