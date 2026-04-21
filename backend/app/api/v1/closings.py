from __future__ import annotations

import csv
import io
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.closings import ClosingStatusReport, ClosingStatusRow
from app.services import audit
from app.services import closings as closing_service
from app.services import leaves as leave_service

JST = ZoneInfo("Asia/Tokyo")

router = APIRouter(prefix="/v1/admin/closings", tags=["admin", "closings"])
exports_router = APIRouter(
    prefix="/v1/admin/exports", tags=["admin", "exports"]
)


def _require_ym(year: int, month: int) -> tuple[int, int]:
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="invalid_month")
    return year, month


# ---------------------------------------------------------------------------
# Status & lifecycle
# ---------------------------------------------------------------------------
@router.get("/status", response_model=ClosingStatusReport)
def status(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> ClosingStatusReport:
    ym = closing_service.year_month_str(year, month)
    rows = closing_service.list_status(db, year=year, month=month)
    out_rows: list[ClosingStatusRow] = []
    for emp, closing in rows:
        out_rows.append(
            ClosingStatusRow(
                employee_id=emp.id,
                employee_name=emp.name,
                employee_email=emp.email,
                year_month=ym,
                closed=bool(closing and closing.closed_at is not None),
                closed_at=closing.closed_at if closing else None,
                total_worked_minutes=closing.total_worked_minutes if closing else 0,
                total_overtime_minutes=closing.total_overtime_minutes if closing else 0,
                working_days=closing.working_days if closing else 0,
            )
        )
    return ClosingStatusReport(year=year, month=month, rows=out_rows)


@router.post("/recompute")
def recompute(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    employee_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
) -> dict:
    _require_ym(year, month)
    from sqlalchemy import select
    from app.models.employee import Employee as EmployeeModel

    if employee_id is not None:
        ids = [employee_id]
    else:
        ids = list(
            db.execute(select(EmployeeModel.id).where(EmployeeModel.active.is_(True)))
            .scalars()
            .all()
        )
    for eid in ids:
        closing_service.recompute_month(db, employee_id=eid, year=year, month=month)
    audit.record_audit(
        db,
        actor_id=admin.id,
        action="closing.recompute",
        target_type="year_month",
        target_id=closing_service.year_month_str(year, month),
        diff={"employee_count": [None, len(ids)]},
    )
    db.commit()
    return {"recomputed": len(ids), "year_month": closing_service.year_month_str(year, month)}


@router.post("/close")
def close(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    employee_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
) -> dict:
    _require_ym(year, month)
    if employee_id is not None:
        try:
            closing_service.close_month(
                db,
                employee_id=employee_id,
                year=year,
                month=month,
                actor_id=admin.id,
            )
        except closing_service.ClosingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from None
        count = 1
    else:
        count = closing_service.close_all(
            db, year=year, month=month, actor_id=admin.id
        )
    audit.record_audit(
        db,
        actor_id=admin.id,
        action="closing.close",
        target_type="year_month",
        target_id=closing_service.year_month_str(year, month),
        diff={"closed_count": [None, count]},
    )
    db.commit()
    return {"closed": count, "year_month": closing_service.year_month_str(year, month)}


@router.post("/reopen")
def reopen(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    employee_id: UUID = Query(...),
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
) -> dict:
    _require_ym(year, month)
    try:
        closing_service.reopen_month(
            db, employee_id=employee_id, year=year, month=month
        )
    except closing_service.ClosingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    audit.record_audit(
        db,
        actor_id=admin.id,
        action="closing.reopen",
        target_type="employee",
        target_id=str(employee_id),
        diff={"year_month": [None, closing_service.year_month_str(year, month)]},
    )
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# CSV exports
# ---------------------------------------------------------------------------
def _csv_response(filename: str, rows: list[list[str]]) -> StreamingResponse:
    buffer = io.StringIO()
    buffer.write("\ufeff")  # BOM for Excel
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@exports_router.get("/monthly.csv")
def export_monthly_csv(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> StreamingResponse:
    rows = closing_service.list_status(db, year=year, month=month)
    out: list[list[str]] = [
        [
            "employee_id",
            "name",
            "email",
            "year_month",
            "working_days",
            "worked_minutes",
            "overtime_minutes",
            "night_minutes",
            "break_minutes",
            "closed",
            "closed_at",
        ]
    ]
    ym = closing_service.year_month_str(year, month)
    for emp, c in rows:
        out.append(
            [
                str(emp.id),
                emp.name,
                emp.email,
                ym,
                str(c.working_days if c else 0),
                str(c.total_worked_minutes if c else 0),
                str(c.total_overtime_minutes if c else 0),
                str(c.total_night_minutes if c else 0),
                str(c.total_break_minutes if c else 0),
                "yes" if (c and c.closed_at) else "no",
                c.closed_at.astimezone(JST).isoformat() if c and c.closed_at else "",
            ]
        )
    return _csv_response(f"attendance_{ym}.csv", out)


@exports_router.get("/leaves.csv")
def export_leaves_csv(
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> StreamingResponse:
    summaries = leave_service.list_summaries(db, year=year)
    out: list[list[str]] = [
        [
            "employee_id",
            "name",
            "email",
            "year",
            "leave_type",
            "granted_days",
            "carried_over_days",
            "used_days",
            "remaining_days",
        ]
    ]
    for s in summaries:
        out.append(
            [
                str(s.employee_id),
                s.employee_name,
                s.employee_email,
                str(s.year),
                s.leave_type,
                str(s.granted_days),
                str(s.carried_over_days),
                str(s.used_days),
                str(s.remaining_days),
            ]
        )
    return _csv_response(f"leaves_{year}.csv", out)
