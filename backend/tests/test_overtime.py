from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.daily_attendance import (
    DailyAttendance,
    DailyAttendanceStatus,
)
from app.models.employee import Employee
from app.models.overtime_alert import OvertimeAlert
from app.services import overtime as overtime_service

JST = ZoneInfo("Asia/Tokyo")


def _add_daily(
    db: Session,
    *,
    employee_id: UUID,
    work_date: date,
    worked_minutes: int,
    overtime_minutes: int,
) -> None:
    db.add(
        DailyAttendance(
            employee_id=employee_id,
            work_date=work_date,
            first_clock_in_at=datetime(
                work_date.year, work_date.month, work_date.day, 9, 0, tzinfo=JST
            ).astimezone(UTC),
            last_clock_out_at=datetime(
                work_date.year, work_date.month, work_date.day, 18, 0, tzinfo=JST
            ).astimezone(UTC),
            worked_minutes=worked_minutes,
            break_minutes=60,
            overtime_minutes=overtime_minutes,
            night_minutes=0,
            status=DailyAttendanceStatus.NORMAL,
        )
    )
    db.commit()


def test_compute_monthly_overtime(db_session: Session, member: Employee) -> None:
    # 3 日分、それぞれ 60 分残業
    for day in (1, 2, 3):
        _add_daily(
            db_session,
            employee_id=member.id,
            work_date=date(2026, 4, day),
            worked_minutes=9 * 60,
            overtime_minutes=60,
        )
    ot, worked, days = overtime_service.compute_monthly_overtime(
        db_session, employee_id=member.id, year=2026, month=4
    )
    assert ot == 180
    assert worked == 27 * 60
    assert days == 3


def test_threshold_alerts_are_sent_once(
    db_session: Session, member: Employee
) -> None:
    # 46 日 × 60 分? easier: one day with huge overtime to cross thresholds deterministically
    # 100h + 60min = 6060 min overtime
    _add_daily(
        db_session,
        employee_id=member.id,
        work_date=date(2026, 4, 1),
        worked_minutes=6060 + 8 * 60,
        overtime_minutes=6060,
    )
    sent = overtime_service.check_and_alert_overtime(
        db_session, employee=member, year=2026, month=4
    )
    db_session.commit()
    # all three thresholds crossed
    assert sent == [45 * 60, 80 * 60, 100 * 60]

    # second run should send nothing new
    sent2 = overtime_service.check_and_alert_overtime(
        db_session, employee=member, year=2026, month=4
    )
    db_session.commit()
    assert sent2 == []

    rows = (
        db_session.execute(
            select(OvertimeAlert).where(OvertimeAlert.employee_id == member.id)
        )
        .scalars()
        .all()
    )
    assert len(rows) == 3


def test_threshold_crossing_incremental(
    db_session: Session, member: Employee
) -> None:
    # Day 1: 45h * 60 min = 2700 overtime (45h exactly) -> should trigger 45h alert
    _add_daily(
        db_session,
        employee_id=member.id,
        work_date=date(2026, 4, 1),
        worked_minutes=2700 + 8 * 60,
        overtime_minutes=2700,
    )
    sent1 = overtime_service.check_and_alert_overtime(
        db_session, employee=member, year=2026, month=4
    )
    db_session.commit()
    assert sent1 == [45 * 60]

    # Day 2 adds more overtime -> crosses 80h
    _add_daily(
        db_session,
        employee_id=member.id,
        work_date=date(2026, 4, 2),
        worked_minutes=8 * 60 + 2400,
        overtime_minutes=2400,  # +40h => total 85h
    )
    sent2 = overtime_service.check_and_alert_overtime(
        db_session, employee=member, year=2026, month=4
    )
    db_session.commit()
    assert sent2 == [80 * 60]


def test_admin_overtime_api(
    client: TestClient, admin_token: str, member_token: str, member: Employee
) -> None:
    # a minimal row to ensure counts
    r = client.get(
        "/api/v1/admin/overtime/monthly?year=2026&month=4",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2026
    assert body["month"] == 4
    assert 45 * 60 in body["thresholds_minutes"]
    assert any(row["employee_email"] == member.email for row in body["rows"])

    # member access forbidden
    r2 = client.get(
        "/api/v1/admin/overtime/monthly?year=2026&month=4",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r2.status_code == 403


def test_overtime_post_request_creation(
    client: TestClient, member_token: str
) -> None:
    payload = {
        "payload": {
            "kind": "overtime_post",
            "target_date": "2026-04-20",
            "actual_minutes": 90,
            "reason": "緊急対応",
        }
    }
    r = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json=payload,
    )
    assert r.status_code == 201, r.text
    assert r.json()["type"] == "overtime_post"
