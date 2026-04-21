from __future__ import annotations

from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmploymentTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    standard_daily_minutes: int
    standard_weekly_minutes: int
    core_start: time | None
    core_end: time | None


class ShiftCreate(BaseModel):
    employee_id: UUID
    work_date: date
    start_time: time
    end_time: time
    break_minutes: int = Field(default=60, ge=0, le=480)


class ShiftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    work_date: date
    start_time: time
    end_time: time
    break_minutes: int


class ShiftMonthlyResponse(BaseModel):
    year: int
    month: int
    shifts: list[ShiftOut]


class FlexSettlementOut(BaseModel):
    employee_id: UUID
    year: int
    month: int
    employment_type_code: str | None
    required_minutes: int
    worked_minutes: int
    surplus_minutes: int
    core_start: time | None
    core_end: time | None
    core_violation_dates: list[date]
    working_days: int


class EmploymentTypeAssign(BaseModel):
    employment_type_id: UUID | None = None
