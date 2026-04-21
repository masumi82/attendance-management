from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.employee import Employee, Role
from app.schemas.shifts import (
    EmploymentTypeAssign,
    EmploymentTypeOut,
    FlexSettlementOut,
    ShiftCreate,
    ShiftMonthlyResponse,
    ShiftOut,
)
from app.services import flex as flex_service
from app.services import shifts as shift_service

JST = ZoneInfo("Asia/Tokyo")

router = APIRouter(prefix="/v1/shifts", tags=["shifts"])
admin_router = APIRouter(prefix="/v1/admin/shifts", tags=["admin", "shifts"])
emp_type_router = APIRouter(
    prefix="/v1/employment-types", tags=["employment-types"]
)


def _resolve_target(current: Employee, employee_id: UUID | None) -> UUID:
    if employee_id is None or employee_id == current.id:
        return current.id
    if current.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="forbidden")
    return employee_id


# ---------------------------------------------------------------------------
# Employment types (read public, write admin)
# ---------------------------------------------------------------------------
@emp_type_router.get("", response_model=list[EmploymentTypeOut])
def list_employment_types(
    db: Session = Depends(get_db),
    _current: Employee = Depends(get_current_user),
) -> list[EmploymentTypeOut]:
    types = shift_service.list_employment_types(db)
    return [EmploymentTypeOut.model_validate(t) for t in types]


@emp_type_router.post(
    "/assign/{employee_id}", response_model=EmploymentTypeOut | None
)
def assign_employment_type(
    employee_id: UUID,
    body: EmploymentTypeAssign,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> EmploymentTypeOut | None:
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="employee_not_found")
    shift_service.assign_employment_type(
        db, employee=emp, employment_type_id=body.employment_type_id
    )
    db.commit()
    if body.employment_type_id is None:
        return None
    from app.models.employment_type import EmploymentType

    et = db.get(EmploymentType, body.employment_type_id)
    return EmploymentTypeOut.model_validate(et) if et else None


# ---------------------------------------------------------------------------
# Shifts
# ---------------------------------------------------------------------------
@router.get("/monthly", response_model=ShiftMonthlyResponse)
def monthly_shifts(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    employee_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> ShiftMonthlyResponse:
    target_id = _resolve_target(current, employee_id)
    shifts = shift_service.list_shifts_month(
        db, employee_id=target_id, year=year, month=month
    )
    return ShiftMonthlyResponse(
        year=year,
        month=month,
        shifts=[ShiftOut.model_validate(s) for s in shifts],
    )


@admin_router.post("", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def upsert_shift(
    payload: ShiftCreate,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> ShiftOut:
    try:
        shift = shift_service.upsert_shift(
            db,
            employee_id=payload.employee_id,
            work_date=payload.work_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            break_minutes=payload.break_minutes,
        )
    except shift_service.ShiftError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    db.commit()
    db.refresh(shift)
    return ShiftOut.model_validate(shift)


@admin_router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shift(
    shift_id: UUID,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> None:
    ok = shift_service.delete_shift(db, shift_id=shift_id)
    if not ok:
        raise HTTPException(status_code=404, detail="shift_not_found")
    db.commit()


# ---------------------------------------------------------------------------
# Flex settlement
# ---------------------------------------------------------------------------
@router.get("/flex", response_model=FlexSettlementOut)
def flex_settlement(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    employee_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> FlexSettlementOut:
    now = datetime.now(JST)
    y = year or now.year
    m = month or now.month
    target_id = _resolve_target(current, employee_id)
    target = db.get(Employee, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="employee_not_found")
    s = flex_service.compute_flex_settlement(db, employee=target, year=y, month=m)
    return FlexSettlementOut(**asdict(s))
