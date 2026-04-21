from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.employee import Employee, Role
from app.schemas.attendance import (
    DailyAttendanceOut,
    MonthlyResponse,
    MonthlyStats,
    PunchOut,
    PunchRequest,
    TodayResponse,
)
from app.services import attendance as attendance_service
from app.services import audit

router = APIRouter(prefix="/v1/attendance", tags=["attendance"])


def _resolve_target(
    current: Employee, employee_id: UUID | None
) -> UUID:
    if employee_id is None or employee_id == current.id:
        return current.id
    if current.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="forbidden"
        )
    return employee_id


def _extract_ip(request: Request) -> str | None:
    if fwd := request.headers.get("x-forwarded-for"):
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/punches", response_model=PunchOut, status_code=status.HTTP_201_CREATED)
def create_punch(
    payload: PunchRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> PunchOut:
    try:
        punch = attendance_service.record_punch(
            db,
            employee_id=current.id,
            punch_type=payload.type,
            ip_address=_extract_ip(request),
        )
    except attendance_service.PunchError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from None

    audit.record_audit(
        db,
        actor_id=current.id,
        action=f"attendance.punch.{payload.type.value}",
        target_type="employee",
        target_id=current.id,
        request=request,
    )
    db.commit()
    db.refresh(punch)
    return PunchOut.model_validate(punch)


@router.get("/today", response_model=TodayResponse)
def get_today(
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
    employee_id: UUID | None = Query(default=None),
) -> TodayResponse:
    target_id = _resolve_target(current, employee_id)
    now = datetime.now(UTC)
    work_date = attendance_service.jst_date(now)
    punches = attendance_service.list_punches(
        db, employee_id=target_id, work_date=work_date
    )
    daily = attendance_service.get_daily(
        db, employee_id=target_id, work_date=work_date
    )
    state = attendance_service.punch_state(punches)
    return TodayResponse(
        work_date=work_date,
        state=state,
        punches=[PunchOut.model_validate(p) for p in punches],
        daily=DailyAttendanceOut.model_validate(daily) if daily else None,
    )


@router.get("/monthly", response_model=MonthlyResponse)
def get_monthly(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
    employee_id: UUID | None = Query(default=None),
) -> MonthlyResponse:
    target_id = _resolve_target(current, employee_id)
    days = attendance_service.list_month(
        db, employee_id=target_id, year=year, month=month
    )
    working = [d for d in days if d.worked_minutes > 0]
    stats = MonthlyStats(
        working_days=len(working),
        total_worked_minutes=sum(d.worked_minutes for d in days),
        total_overtime_minutes=sum(d.overtime_minutes for d in days),
        total_night_minutes=sum(d.night_minutes for d in days),
        total_break_minutes=sum(d.break_minutes for d in days),
    )
    return MonthlyResponse(
        year=year,
        month=month,
        days=[DailyAttendanceOut.model_validate(d) for d in days],
        stats=stats,
    )
