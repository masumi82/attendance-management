from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.overtime import OvertimeReport, OvertimeRowOut
from app.services import overtime as overtime_service

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/overtime/monthly", response_model=OvertimeReport)
def monthly_overtime(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> OvertimeReport:
    rows = overtime_service.list_monthly_overtime(db, year=year, month=month)
    return OvertimeReport(
        year=year,
        month=month,
        thresholds_minutes=overtime_service.THRESHOLDS_MINUTES,
        rows=[
            OvertimeRowOut(
                employee_id=r.employee_id,
                employee_name=r.employee_name,
                employee_email=r.employee_email,
                total_overtime_minutes=r.total_overtime_minutes,
                total_worked_minutes=r.total_worked_minutes,
                working_days=r.working_days,
                alerts_sent=r.alerts_sent,
            )
            for r in rows
        ],
    )
