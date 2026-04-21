from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.attendance_punch import PunchType
from app.models.request import RequestStatus, RequestType


class PunchFixPayload(BaseModel):
    kind: Literal["punch_fix"] = "punch_fix"
    target_date: date
    punch_type: PunchType
    punched_at: datetime
    reason: str = Field(min_length=1, max_length=500)


class OvertimePrePayload(BaseModel):
    kind: Literal["overtime_pre"] = "overtime_pre"
    target_date: date
    planned_minutes: int = Field(gt=0, le=600)
    reason: str = Field(min_length=1, max_length=500)


class OvertimePostPayload(BaseModel):
    kind: Literal["overtime_post"] = "overtime_post"
    target_date: date
    actual_minutes: int = Field(gt=0, le=600)
    reason: str = Field(min_length=1, max_length=500)


class LeavePayload(BaseModel):
    kind: Literal["leave"] = "leave"
    start_date: date
    end_date: date
    leave_kind: Literal["full_day", "half_day_am", "half_day_pm"]
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("end_date")
    @classmethod
    def _check_range(cls, v: date, info) -> date:  # noqa: ANN001
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date_before_start")
        return v


RequestPayload = Annotated[
    Union[
        PunchFixPayload,
        OvertimePrePayload,
        OvertimePostPayload,
        LeavePayload,
    ],
    Field(discriminator="kind"),
]


class RequestCreate(BaseModel):
    payload: RequestPayload
    comment: str | None = Field(default=None, max_length=500)


class DecisionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    approver_id: UUID | None
    step: int
    decision: str
    decided_at: datetime | None
    comment: str | None


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    employee_id: UUID
    type: RequestType
    status: RequestStatus
    target_date: date | None
    payload: dict
    requester_comment: str | None
    submitted_at: datetime
    decided_at: datetime | None


class RequestDetail(RequestOut):
    approvals: list[ApprovalOut] = []


class ApprovalQueueItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    approval_id: UUID
    request: RequestOut
    step: int
    requested_by_name: str
    requested_by_email: str
