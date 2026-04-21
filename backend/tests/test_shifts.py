from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.attendance_punch import PunchSource, PunchType
from app.models.employee import Employee
from app.services import attendance as attendance_service
from app.services import flex as flex_service

JST = ZoneInfo("Asia/Tokyo")


def _jst(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=JST).astimezone(UTC)


# ---------------------------------------------------------------------------
# Employment types (seeded via migration)
# ---------------------------------------------------------------------------
def test_employment_types_seeded(client: TestClient, admin_token: str) -> None:
    r = client.get(
        "/api/v1/employment-types",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    codes = {t["code"] for t in r.json()}
    assert {"standard", "shift", "flex"}.issubset(codes)


def test_assign_employment_type(
    client: TestClient, admin_token: str, member: Employee
) -> None:
    types = client.get(
        "/api/v1/employment-types",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    flex = next(t for t in types if t["code"] == "flex")

    r = client.post(
        f"/api/v1/employment-types/assign/{member.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"employment_type_id": flex["id"]},
    )
    assert r.status_code == 200
    assert r.json()["code"] == "flex"


# ---------------------------------------------------------------------------
# Shift CRUD
# ---------------------------------------------------------------------------
def test_shift_upsert_and_list(
    client: TestClient, admin_token: str, member: Employee, member_token: str
) -> None:
    r = client.post(
        "/api/v1/admin/shifts",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "employee_id": str(member.id),
            "work_date": "2026-04-20",
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "break_minutes": 60,
        },
    )
    assert r.status_code == 201
    assert r.json()["start_time"] == "09:00:00"

    # upsert: update end_time
    r2 = client.post(
        "/api/v1/admin/shifts",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "employee_id": str(member.id),
            "work_date": "2026-04-20",
            "start_time": "10:00:00",
            "end_time": "19:00:00",
            "break_minutes": 60,
        },
    )
    assert r2.status_code == 201
    assert r2.json()["start_time"] == "10:00:00"

    # member lists monthly
    r3 = client.get(
        "/api/v1/shifts/monthly?year=2026&month=4",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r3.status_code == 200
    body = r3.json()
    assert len(body["shifts"]) == 1
    assert body["shifts"][0]["end_time"] == "19:00:00"


def test_shift_end_before_start_rejected(
    client: TestClient, admin_token: str, member: Employee
) -> None:
    r = client.post(
        "/api/v1/admin/shifts",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "employee_id": str(member.id),
            "work_date": "2026-04-21",
            "start_time": "18:00:00",
            "end_time": "09:00:00",
            "break_minutes": 60,
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "end_before_start"


def test_member_cannot_create_shift(
    client: TestClient, member_token: str, member: Employee
) -> None:
    r = client.post(
        "/api/v1/admin/shifts",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "employee_id": str(member.id),
            "work_date": "2026-04-22",
            "start_time": "09:00:00",
            "end_time": "18:00:00",
        },
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Flex settlement
# ---------------------------------------------------------------------------
def test_flex_settlement_surplus_and_violations(
    client: TestClient,
    admin_token: str,
    member: Employee,
    member_token: str,
    db_session: Session,
) -> None:
    # Assign flex type
    types = client.get(
        "/api/v1/employment-types",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    flex = next(t for t in types if t["code"] == "flex")
    client.post(
        f"/api/v1/employment-types/assign/{member.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"employment_type_id": flex["id"]},
    )

    # Day 1 (Mon 2026-04-20): worked 9h (9-18) — covers core 10-15
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_IN,
        punched_at=_jst(2026, 4, 20, 9, 0),
        source=PunchSource.WEB,
    )
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_OUT,
        punched_at=_jst(2026, 4, 20, 18, 0),
        source=PunchSource.WEB,
    )
    # Day 2 (Tue 2026-04-21): 11:00-14:00 - VIOLATES core 10-15 (late start, early end)
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_IN,
        punched_at=_jst(2026, 4, 21, 11, 0),
        source=PunchSource.WEB,
    )
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_OUT,
        punched_at=_jst(2026, 4, 21, 14, 0),
        source=PunchSource.WEB,
    )
    db_session.commit()

    # Self flex settlement
    r = client.get(
        "/api/v1/shifts/flex?year=2026&month=4",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["employment_type_code"] == "flex"
    # 2026-04 has 22 business days => 22 * 480 = 10560 required
    assert body["required_minutes"] == 10560
    # worked = 540 + 180 = 720
    assert body["worked_minutes"] == 720
    assert body["surplus_minutes"] == 720 - 10560
    assert "2026-04-21" in body["core_violation_dates"]
    assert "2026-04-20" not in body["core_violation_dates"]


def test_flex_service_no_employment_type(
    db_session: Session, member: Employee
) -> None:
    # No employment type assigned
    s = flex_service.compute_flex_settlement(
        db_session, employee=member, year=2026, month=4
    )
    assert s.employment_type_code is None
    assert s.required_minutes == 22 * 480  # still uses default 480
    assert s.core_violation_dates == []
