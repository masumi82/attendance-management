from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance_punch import AttendancePunch, PunchSource
from app.models.daily_attendance import DailyAttendance, DailyAttendanceStatus
from app.models.employee import Employee, Role
from app.models.request import Approval, Request, RequestStatus, RequestType
from app.schemas.request import RequestCreate, RequestPayload
from app.services import attendance as attendance_service
from app.services import leaves as leave_service
from app.services.notifier import broadcast


class RequestError(Exception):
    pass


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def _payload_kind_to_type(payload: RequestPayload) -> RequestType:
    return {
        "punch_fix": RequestType.PUNCH_FIX,
        "overtime_pre": RequestType.OVERTIME_PRE,
        "overtime_post": RequestType.OVERTIME_POST,
        "leave": RequestType.LEAVE,
    }[payload.kind]


def _payload_target_date(payload: RequestPayload) -> date | None:
    if payload.kind in ("punch_fix", "overtime_pre", "overtime_post"):
        return payload.target_date  # type: ignore[union-attr]
    if payload.kind == "leave":
        return payload.start_date  # type: ignore[union-attr]
    return None


def _approver_recipients(db: Session) -> list[str]:
    stmt = select(Employee.email).where(
        Employee.active.is_(True),
        Employee.role.in_([Role.ADMIN, Role.APPROVER]),
    )
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
def create_request(
    db: Session, *, employee: Employee, payload: RequestCreate
) -> Request:
    req = Request(
        employee_id=employee.id,
        type=_payload_kind_to_type(payload.payload),
        status=RequestStatus.PENDING,
        target_date=_payload_target_date(payload.payload),
        payload=payload.payload.model_dump(mode="json"),
        requester_comment=payload.comment,
        submitted_at=datetime.now(UTC),
    )
    db.add(req)
    db.flush()

    approval = Approval(
        request_id=req.id,
        step=1,
        decision="pending",
    )
    db.add(approval)
    db.flush()

    broadcast(
        _approver_recipients(db),
        subject=f"[勤怠管理] 申請が提出されました: {req.type.value}",
        body=(
            f"申請者: {employee.name} <{employee.email}>\n"
            f"種別: {req.type.value}\n"
            f"対象日: {req.target_date}\n"
            f"ペイロード: {req.payload}\n"
            f"コメント: {req.requester_comment or '-'}\n"
        ),
    )
    return req


def cancel_request(
    db: Session, *, request_obj: Request, current: Employee
) -> Request:
    if request_obj.employee_id != current.id:
        raise RequestError("not_owner")
    if request_obj.status != RequestStatus.PENDING:
        raise RequestError("not_cancelable")
    request_obj.status = RequestStatus.CANCELED
    request_obj.decided_at = datetime.now(UTC)
    # mark open approvals as canceled-equivalent (keep "pending" decision but freeze)
    db.flush()
    return request_obj


def list_own_requests(db: Session, *, employee_id: UUID) -> list[Request]:
    stmt = (
        select(Request)
        .where(Request.employee_id == employee_id)
        .order_by(Request.submitted_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_request_with_approvals(
    db: Session, *, request_id: UUID
) -> tuple[Request, list[Approval]] | None:
    req = db.get(Request, request_id)
    if req is None:
        return None
    stmt = (
        select(Approval)
        .where(Approval.request_id == request_id)
        .order_by(Approval.step.asc(), Approval.created_at.asc())
    )
    approvals = list(db.execute(stmt).scalars().all())
    return req, approvals


def approval_queue(db: Session) -> list[tuple[Approval, Request, Employee]]:
    stmt = (
        select(Approval, Request, Employee)
        .join(Request, Request.id == Approval.request_id)
        .join(Employee, Employee.id == Request.employee_id)
        .where(Approval.decision == "pending")
        .where(Request.status == RequestStatus.PENDING)
        .order_by(Request.submitted_at.asc())
    )
    return [tuple(row) for row in db.execute(stmt).all()]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Decisions (approve/reject) with side-effects
# ---------------------------------------------------------------------------
def decide(
    db: Session,
    *,
    approval: Approval,
    decision: str,
    approver: Employee,
    comment: str | None,
) -> tuple[Request, Approval]:
    if decision not in ("approved", "rejected"):
        raise RequestError("invalid_decision")
    if approval.decision != "pending":
        raise RequestError("already_decided")

    req = db.get(Request, approval.request_id)
    if req is None:
        raise RequestError("request_not_found")
    if req.status != RequestStatus.PENDING:
        raise RequestError("request_not_pending")
    if approver.id == req.employee_id:
        raise RequestError("self_approval_forbidden")

    approval.decision = decision
    approval.approver_id = approver.id
    approval.decided_at = datetime.now(UTC)
    approval.comment = comment

    req.status = (
        RequestStatus.APPROVED if decision == "approved" else RequestStatus.REJECTED
    )
    req.decided_at = approval.decided_at

    if decision == "approved":
        _apply_approval_effects(db, req)

    db.flush()

    # notify requester
    requester = db.get(Employee, req.employee_id)
    if requester is not None:
        broadcast(
            [requester.email],
            subject=f"[勤怠管理] 申請が{'承認' if decision == 'approved' else '却下'}されました",
            body=(
                f"種別: {req.type.value}\n"
                f"対象日: {req.target_date}\n"
                f"承認者: {approver.name} <{approver.email}>\n"
                f"コメント: {comment or '-'}\n"
            ),
        )

    return req, approval


# ---------------------------------------------------------------------------
# Side-effects per type
# ---------------------------------------------------------------------------
def _apply_approval_effects(db: Session, request_obj: Request) -> None:
    if request_obj.type == RequestType.PUNCH_FIX:
        _apply_punch_fix(db, request_obj)
    elif request_obj.type == RequestType.LEAVE:
        _apply_leave(db, request_obj)
    # overtime_pre: no side-effect (Phase 4 aggregates)


def _apply_punch_fix(db: Session, request_obj: Request) -> None:
    payload = request_obj.payload
    target_date = date.fromisoformat(payload["target_date"])
    punched_at = datetime.fromisoformat(payload["punched_at"])
    if punched_at.tzinfo is None:
        punched_at = punched_at.replace(tzinfo=UTC)

    # Block additions to a closed month. Admin correction on a closed month
    # must first reopen the month to preserve audit integrity.
    if attendance_service._is_closed(
        db, employee_id=request_obj.employee_id, work_date=target_date
    ):
        raise RequestError("month_closed")

    # additive correction: insert an admin-source punch at the requested time
    punch = AttendancePunch(
        employee_id=request_obj.employee_id,
        work_date=target_date,
        punched_at=punched_at,
        type=payload["punch_type"],
        source=PunchSource.ADMIN,
        ip_address=None,
    )
    db.add(punch)
    db.flush()

    attendance_service.recompute_daily(
        db,
        employee_id=request_obj.employee_id,
        work_date=target_date,
        now=datetime.now(UTC),
    )


def _apply_leave(db: Session, request_obj: Request) -> None:
    payload = request_obj.payload
    start = date.fromisoformat(payload["start_date"])
    end = date.fromisoformat(payload["end_date"])
    if end < start:
        return
    leave_kind = payload.get("leave_kind", "full_day")

    days = leave_service.count_consumed_days(
        start=start, end=end, leave_kind=leave_kind
    )
    try:
        leave_service.deduct_leave(
            db,
            employee_id=request_obj.employee_id,
            year=start.year,
            days=days,
        )
    except leave_service.LeaveError as exc:
        raise RequestError(f"leave_{exc}") from None

    cur = start
    while cur <= end:
        _upsert_leave_day(
            db,
            employee_id=request_obj.employee_id,
            work_date=cur,
            leave_kind=leave_kind,
        )
        cur = cur + timedelta(days=1)


def _upsert_leave_day(
    db: Session, *, employee_id: UUID, work_date: date, leave_kind: str = "full_day"
) -> DailyAttendance:
    stmt = (
        select(DailyAttendance)
        .where(DailyAttendance.employee_id == employee_id)
        .where(DailyAttendance.work_date == work_date)
    )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        row = DailyAttendance(employee_id=employee_id, work_date=work_date)
        db.add(row)

    if leave_kind == "full_day":
        row.status = DailyAttendanceStatus.LEAVE
        row.worked_minutes = 0
        row.overtime_minutes = 0
        row.night_minutes = 0
        row.break_minutes = 0
        row.first_clock_in_at = None
        row.last_clock_out_at = None
    else:
        # 半休は既存の実打刻集計（worked_minutes 等）を保持し、
        # status のみ LEAVE にする。集計は recompute_daily に委ねる。
        row.status = DailyAttendanceStatus.LEAVE
    db.flush()
    return row


__all__ = [
    "RequestError",
    "approval_queue",
    "cancel_request",
    "create_request",
    "decide",
    "get_request_with_approvals",
    "list_own_requests",
]
