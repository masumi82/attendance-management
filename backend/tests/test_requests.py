from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_attendance import DailyAttendance, DailyAttendanceStatus
from app.models.employee import Employee
from app.services import leaves as leave_service


def _punch_fix_payload(**overrides) -> dict:
    base = {
        "payload": {
            "kind": "punch_fix",
            "target_date": "2026-04-20",
            "punch_type": "clock_in",
            "punched_at": "2026-04-20T09:00:00+09:00",
            "reason": "打刻忘れ",
        },
        "comment": "朝の打刻を忘れました",
    }
    base.update(overrides)
    return base


def _leave_payload() -> dict:
    return {
        "payload": {
            "kind": "leave",
            "start_date": "2026-04-22",
            "end_date": "2026-04-22",
            "leave_kind": "full_day",
            "reason": "私用",
        },
        "comment": None,
    }


def _overtime_payload() -> dict:
    return {
        "payload": {
            "kind": "overtime_pre",
            "target_date": "2026-04-20",
            "planned_minutes": 120,
            "reason": "リリース対応",
        },
        "comment": None,
    }


# ---------------------------------------------------------------------------
# Creation / Listing / Cancel
# ---------------------------------------------------------------------------
def test_create_and_list_own_requests(
    client: TestClient, member_token: str
) -> None:
    h = {"Authorization": f"Bearer {member_token}"}
    r = client.post("/api/v1/requests", headers=h, json=_punch_fix_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["type"] == "punch_fix"
    assert body["status"] == "pending"
    assert len(body["approvals"]) == 1

    lst = client.get("/api/v1/requests", headers=h).json()
    assert len(lst) == 1
    assert lst[0]["id"] == body["id"]


def test_cancel_own_pending(
    client: TestClient, member_token: str
) -> None:
    h = {"Authorization": f"Bearer {member_token}"}
    created = client.post("/api/v1/requests", headers=h, json=_punch_fix_payload()).json()

    r = client.post(f"/api/v1/requests/{created['id']}/cancel", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "canceled"

    # cancel again -> 409
    again = client.post(f"/api/v1/requests/{created['id']}/cancel", headers=h)
    assert again.status_code == 409


def test_member_cannot_view_other_request(
    client: TestClient,
    member_token: str,
    admin_token: str,
    admin: Employee,
) -> None:
    # create with admin, view with member
    created = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_overtime_payload(),
    ).json()
    r = client.get(
        f"/api/v1/requests/{created['id']}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Approval queue & decisions
# ---------------------------------------------------------------------------
def test_queue_requires_approver_role(
    client: TestClient, member_token: str
) -> None:
    r = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r.status_code == 403


def test_approve_punch_fix_creates_punch_and_recomputes(
    client: TestClient,
    member_token: str,
    approver_token: str,
    db_session: Session,
    member: Employee,
) -> None:
    # member が打刻忘れを申請
    payload = _punch_fix_payload()
    created = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json=payload,
    ).json()

    # 承認キューから取得
    queue = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {approver_token}"},
    ).json()
    assert any(item["request"]["id"] == created["id"] for item in queue)
    target = next(item for item in queue if item["request"]["id"] == created["id"])

    r = client.post(
        f"/api/v1/approvals/{target['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": "OK"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    # 追加で clock_out を申請して承認（8h ちょうど）
    out_payload = _punch_fix_payload(
        payload={
            "kind": "punch_fix",
            "target_date": "2026-04-20",
            "punch_type": "clock_out",
            "punched_at": "2026-04-20T18:00:00+09:00",
            "reason": "退勤忘れ",
        }
    )
    out_created = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json=out_payload,
    ).json()
    q2 = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {approver_token}"},
    ).json()
    out_target = next(
        item for item in q2 if item["request"]["id"] == out_created["id"]
    )
    client.post(
        f"/api/v1/approvals/{out_target['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": None},
    )

    # daily_attendance が再計算されているか確認 (8h 勤務 + 0 休憩)
    daily = db_session.execute(
        select(DailyAttendance)
        .where(DailyAttendance.employee_id == member.id)
        .where(DailyAttendance.work_date == date(2026, 4, 20))
    ).scalar_one()
    assert daily.status is DailyAttendanceStatus.NORMAL
    assert daily.worked_minutes == 9 * 60  # 09:00-18:00 = 9h (休憩なし）


def test_approve_leave_marks_daily_as_leave(
    client: TestClient,
    member_token: str,
    approver_token: str,
    db_session: Session,
    member: Employee,
) -> None:
    # Leave approval requires an existing balance; grant first.
    leave_service.grant_annual_leave(db_session, employee=member, year=2026)
    db_session.commit()

    created = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json=_leave_payload(),
    ).json()
    queue = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {approver_token}"},
    ).json()
    target = next(item for item in queue if item["request"]["id"] == created["id"])

    r = client.post(
        f"/api/v1/approvals/{target['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": None},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    daily = db_session.execute(
        select(DailyAttendance)
        .where(DailyAttendance.employee_id == member.id)
        .where(DailyAttendance.work_date == date(2026, 4, 22))
    ).scalar_one()
    assert daily.status is DailyAttendanceStatus.LEAVE


def test_reject_sets_status(
    client: TestClient,
    member_token: str,
    approver_token: str,
) -> None:
    created = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json=_overtime_payload(),
    ).json()
    queue = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {approver_token}"},
    ).json()
    target = next(item for item in queue if item["request"]["id"] == created["id"])

    r = client.post(
        f"/api/v1/approvals/{target['approval_id']}/reject",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": "事前相談が必要"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


def test_double_decision_rejected(
    client: TestClient,
    member_token: str,
    approver_token: str,
) -> None:
    created = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json=_overtime_payload(),
    ).json()
    queue = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {approver_token}"},
    ).json()
    target = next(item for item in queue if item["request"]["id"] == created["id"])

    client.post(
        f"/api/v1/approvals/{target['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": None},
    )
    r = client.post(
        f"/api/v1/approvals/{target['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": None},
    )
    assert r.status_code == 409
