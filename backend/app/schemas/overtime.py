from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class OvertimeRowOut(BaseModel):
    employee_id: UUID
    employee_name: str
    employee_email: str
    total_overtime_minutes: int
    total_worked_minutes: int
    working_days: int
    alerts_sent: list[int]  # thresholds in minutes


class OvertimeReport(BaseModel):
    year: int
    month: int
    thresholds_minutes: list[int]
    rows: list[OvertimeRowOut]
