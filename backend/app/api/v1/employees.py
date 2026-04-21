from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeOut, EmployeeUpdate
from app.services import audit, employee as employee_service

router = APIRouter(prefix="/v1/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> list[Employee]:
    return employee_service.list_employees(db)


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
) -> Employee:
    try:
        created = employee_service.create_employee(db, payload)
    except employee_service.EmployeeServiceError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None

    audit.record_audit(
        db,
        actor_id=admin.id,
        action="employee.create",
        target_type="employee",
        target_id=created.id,
        diff={
            "email": [None, created.email],
            "role": [None, created.role.value],
        },
        request=request,
    )
    db.commit()
    db.refresh(created)
    return created


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: UUID,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> Employee:
    target = employee_service.get_employee(db, employee_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="employee_not_found")
    return target


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: UUID,
    payload: EmployeeUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
) -> Employee:
    target = employee_service.get_employee(db, employee_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="employee_not_found")

    updated, diff = employee_service.update_employee(db, target, payload)
    if diff:
        audit.record_audit(
            db,
            actor_id=admin.id,
            action="employee.update",
            target_type="employee",
            target_id=updated.id,
            diff=diff,
            request=request,
        )
    db.commit()
    db.refresh(updated)
    return updated
