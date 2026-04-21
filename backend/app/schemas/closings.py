from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MonthlyClosingOut(BaseModel):
    id: UUID
    employee_id: UUID
    year_month: str
    total_worked_minutes: int
    total_overtime_minutes: int
    total_night_minutes: int
    total_break_minutes: int
    working_days: int
    closed_at: datetime | None
    closed_by_id: UUID | None


class ClosingStatusRow(BaseModel):
    employee_id: UUID
    employee_name: str
    employee_email: str
    year_month: str
    closed: bool
    closed_at: datetime | None
    total_worked_minutes: int
    total_overtime_minutes: int
    working_days: int


class ClosingStatusReport(BaseModel):
    year: int
    month: int
    rows: list[ClosingStatusRow]
