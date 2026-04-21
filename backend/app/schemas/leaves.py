from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class LeaveBalanceSummary(BaseModel):
    employee_id: UUID
    employee_name: str
    employee_email: str
    year: int
    leave_type: str
    granted_days: Decimal
    used_days: Decimal
    carried_over_days: Decimal
    remaining_days: Decimal


class LeaveBalanceReport(BaseModel):
    year: int
    rows: list[LeaveBalanceSummary]


class GrantRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)


class GrantOneRequest(BaseModel):
    employee_id: UUID
    year: int = Field(ge=2000, le=2100)
    days: Decimal = Field(ge=0, le=60, decimal_places=1)


class CarryOverRequest(BaseModel):
    from_year: int = Field(ge=2000, le=2100)
