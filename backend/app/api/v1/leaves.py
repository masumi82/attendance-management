from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.leaves import (
    CarryOverRequest,
    GrantOneRequest,
    GrantRequest,
    LeaveBalanceReport,
    LeaveBalanceSummary,
)
from app.services import leaves as leave_service

JST = ZoneInfo("Asia/Tokyo")

router = APIRouter(prefix="/v1/leaves", tags=["leaves"])
admin_router = APIRouter(prefix="/v1/admin/leaves", tags=["admin", "leaves"])


def _current_year() -> int:
    return datetime.now(JST).year


@router.get("/balance", response_model=LeaveBalanceSummary)
def get_balance(
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> LeaveBalanceSummary:
    summary = leave_service.get_summary(
        db, employee=current, year=year or _current_year()
    )
    db.commit()
    return LeaveBalanceSummary(**asdict(summary))


@admin_router.get("/balances", response_model=LeaveBalanceReport)
def list_balances(
    year: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> LeaveBalanceReport:
    summaries = leave_service.list_summaries(db, year=year)
    db.commit()
    return LeaveBalanceReport(
        year=year,
        rows=[LeaveBalanceSummary(**asdict(s)) for s in summaries],
    )


@admin_router.post("/grant-all", status_code=200)
def grant_all(
    body: GrantRequest,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> dict:
    count = leave_service.grant_all(db, year=body.year)
    db.commit()
    return {"granted_for_employees": count, "year": body.year}


@admin_router.post("/grant", status_code=200)
def grant_one(
    body: GrantOneRequest,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> dict:
    balance = leave_service.set_granted_days(
        db,
        employee_id=body.employee_id,
        year=body.year,
        days=body.days,
    )
    db.commit()
    return {
        "employee_id": str(body.employee_id),
        "year": body.year,
        "granted_days": str(balance.granted_days),
    }


@admin_router.post("/carryover", status_code=200)
def carryover(
    body: CarryOverRequest,
    db: Session = Depends(get_db),
    _admin: Employee = Depends(require_admin),
) -> dict:
    moved = leave_service.carry_over(db, from_year=body.from_year)
    db.commit()
    return {"moved": moved, "from_year": body.from_year, "to_year": body.from_year + 1}
