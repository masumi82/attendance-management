"""Regression tests for Critical findings B1-B7 from the Phase 7 review."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance_punch import PunchType
from app.models.daily_attendance import DailyAttendance, DailyAttendanceStatus
from app.models.employee import Employee
from app.models.leave_balance import LeaveBalance
from app.models.revoked_access_token import RevokedAccessToken
from app.services import attendance as attendance_service
from app.services import closings as closing_service
from app.services import leaves as leave_service

JST = ZoneInfo("Asia/Tokyo")


def _jst(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=JST).astimezone(UTC)


# ---------------------------------------------------------------------------
# B1: Approved punch_fix must not bypass month closure
# ---------------------------------------------------------------------------
def test_b1_punch_fix_blocked_on_closed_month(
    client: TestClient,
    approver_token: str,
    member_token: str,
    member: Employee,
    db_session: Session,
) -> None:
    # Seed an April punch and close the month
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_IN,
        punched_at=_jst(2026, 4, 20, 9, 0),
    )
    db_session.commit()
    closing_service.close_month(
        db_session, employee_id=member.id, year=2026, month=4, actor_id=member.id
    )
    db_session.commit()

    # member submits a punch_fix for the closed month
    create = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "payload": {
                "kind": "punch_fix",
                "target_date": "2026-04-20",
                "punch_type": "clock_out",
                "punched_at": "2026-04-20T18:00:00+09:00",
                "reason": "退勤忘れ",
            },
            "comment": None,
        },
    )
    assert create.status_code == 201

    # approver tries to approve → must 409 month_closed
    queue = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {approver_token}"},
    ).json()
    target = next(
        item for item in queue if item["request"]["id"] == create.json()["id"]
    )
    r = client.post(
        f"/api/v1/approvals/{target['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": None},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "month_closed"


# ---------------------------------------------------------------------------
# B3: Half-day leave must preserve the day's worked minutes
# ---------------------------------------------------------------------------
def test_b3_half_day_leave_preserves_worked_minutes(
    client: TestClient,
    member_token: str,
    approver_token: str,
    member: Employee,
    db_session: Session,
) -> None:
    # member works 4 hours in the morning
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_IN,
        punched_at=_jst(2026, 4, 23, 9, 0),
    )
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_OUT,
        punched_at=_jst(2026, 4, 23, 13, 0),
    )
    db_session.commit()

    # grant leave balance so deduction succeeds
    leave_service.grant_annual_leave(db_session, employee=member, year=2026)
    db_session.commit()

    # Submit half-day (PM) leave for the same date
    create = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "payload": {
                "kind": "leave",
                "start_date": "2026-04-23",
                "end_date": "2026-04-23",
                "leave_kind": "half_day_pm",
                "reason": "通院",
            },
            "comment": None,
        },
    )
    assert create.status_code == 201

    queue = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {approver_token}"},
    ).json()
    target = next(
        item for item in queue if item["request"]["id"] == create.json()["id"]
    )
    r = client.post(
        f"/api/v1/approvals/{target['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": None},
    )
    assert r.status_code == 200

    daily = db_session.execute(
        select(DailyAttendance).where(
            DailyAttendance.employee_id == member.id,
            DailyAttendance.work_date == date_of("2026-04-23"),
        )
    ).scalar_one()
    # status marks leave but worked minutes for the morning are preserved
    assert daily.status is DailyAttendanceStatus.LEAVE
    assert daily.worked_minutes == 4 * 60


def date_of(iso: str):
    from datetime import date as _d
    return _d.fromisoformat(iso)


# ---------------------------------------------------------------------------
# B4: carry_over is idempotent
# ---------------------------------------------------------------------------
def test_b4_carry_over_is_idempotent(
    db_session: Session, member: Employee
) -> None:
    # Grant 20 days for 2025, use 5 → remaining 15
    leave_service.grant_annual_leave(db_session, employee=member, year=2025)
    bal = db_session.execute(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == member.id,
            LeaveBalance.year == 2025,
        )
    ).scalar_one()
    bal.granted_days = Decimal("20")
    bal.used_days = Decimal("5")
    db_session.commit()

    leave_service.carry_over(db_session, from_year=2025)
    db_session.commit()

    after_first = db_session.execute(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == member.id,
            LeaveBalance.year == 2026,
        )
    ).scalar_one()
    assert after_first.carried_over_days == Decimal("15")

    # run again → must stay at 15, not 30
    leave_service.carry_over(db_session, from_year=2025)
    db_session.commit()

    after_second = db_session.execute(
        select(LeaveBalance).where(
            LeaveBalance.employee_id == member.id,
            LeaveBalance.year == 2026,
        )
    ).scalar_one()
    assert after_second.carried_over_days == Decimal("15")


# ---------------------------------------------------------------------------
# B5: approver cannot approve their own request
# ---------------------------------------------------------------------------
def test_b5_self_approval_forbidden(
    client: TestClient,
    approver_token: str,
) -> None:
    # approver submits an overtime_pre request
    create = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={
            "payload": {
                "kind": "overtime_pre",
                "target_date": "2026-04-23",
                "planned_minutes": 90,
                "reason": "リリース対応",
            },
            "comment": None,
        },
    )
    assert create.status_code == 201

    # approver sees own request in queue, tries to self-approve
    queue = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {approver_token}"},
    ).json()
    target = next(
        item for item in queue if item["request"]["id"] == create.json()["id"]
    )
    r = client.post(
        f"/api/v1/approvals/{target['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": None},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "self_approval_forbidden"


# ---------------------------------------------------------------------------
# B6: access token becomes unusable after logout (JTI denylist)
# ---------------------------------------------------------------------------
def test_b6_access_token_revoked_on_logout(
    client: TestClient,
    member: Employee,
    db_session: Session,
) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": "MemberPass1!"},
    )
    assert login.status_code == 200
    tokens = login.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # access works
    ok = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert ok.status_code == 200

    # logout revokes both refresh and access JTI
    out = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
        json={"refresh_token": refresh},
    )
    assert out.status_code == 204

    # A row must exist in the denylist
    db_session.expire_all()
    count = db_session.execute(select(RevokedAccessToken)).scalars().all()
    assert len(count) == 1

    # The same access token is now unusable
    reused = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert reused.status_code == 401
    assert reused.json()["detail"] == "token_revoked"


# ---------------------------------------------------------------------------
# B7: refresh-token reuse detection revokes all sessions
# ---------------------------------------------------------------------------
def test_b7_refresh_reuse_revokes_all_sessions(
    client: TestClient,
    member: Employee,
) -> None:
    # Login once
    login = client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": "MemberPass1!"},
    ).json()
    old_refresh = login["refresh_token"]

    # Legitimately rotate → old_refresh is now revoked, new_refresh is active
    rotate = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert rotate.status_code == 200
    new_refresh = rotate.json()["refresh_token"]

    # Login from a second device to obtain a parallel session
    second = client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": "MemberPass1!"},
    ).json()
    second_refresh = second["refresh_token"]

    # Attacker replays the old (already-revoked) refresh token
    replay = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert replay.status_code == 401
    assert replay.json()["detail"] == "refresh_reused"

    # Reuse detection must revoke ALL of the user's active sessions,
    # including the new_refresh and the second device's session.
    r1 = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_refresh}
    )
    r2 = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second_refresh}
    )
    assert r1.status_code == 401
    assert r2.status_code == 401
