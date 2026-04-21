from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.attendance_punch import PunchType
from app.models.employee import Employee
from app.services import attendance as attendance_service
from app.services import closings as closing_service

JST = ZoneInfo("Asia/Tokyo")


def _jst(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=JST).astimezone(UTC)


# ---------- Departments ----------
def test_department_crud(client: TestClient, admin_token: str) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post(
        "/api/v1/admin/departments", headers=h, json={"name": "開発", "code": "DEV"}
    )
    assert r.status_code == 201
    dept_id = r.json()["id"]

    # duplicate
    r2 = client.post(
        "/api/v1/admin/departments", headers=h, json={"name": "開発", "code": "DEV"}
    )
    assert r2.status_code == 409

    # update
    r3 = client.patch(
        f"/api/v1/admin/departments/{dept_id}", headers=h, json={"name": "開発部"}
    )
    assert r3.status_code == 200
    assert r3.json()["name"] == "開発部"

    # list
    r4 = client.get("/api/v1/departments", headers=h)
    assert r4.status_code == 200
    assert any(d["id"] == dept_id for d in r4.json())

    # delete
    r5 = client.delete(f"/api/v1/admin/departments/{dept_id}", headers=h)
    assert r5.status_code == 204


# ---------- Holidays ----------
def test_holiday_crud(client: TestClient, admin_token: str) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    r = client.post(
        "/api/v1/admin/holidays",
        headers=h,
        json={"date": "2026-05-03", "name": "憲法記念日", "type": "national"},
    )
    assert r.status_code == 201
    hid = r.json()["id"]

    # duplicate date
    r2 = client.post(
        "/api/v1/admin/holidays",
        headers=h,
        json={"date": "2026-05-03", "name": "憲法記念日", "type": "national"},
    )
    assert r2.status_code == 409

    # list 2026
    r3 = client.get("/api/v1/holidays?year=2026", headers=h)
    assert r3.status_code == 200
    assert any(x["id"] == hid for x in r3.json())

    r4 = client.delete(f"/api/v1/admin/holidays/{hid}", headers=h)
    assert r4.status_code == 204


def test_member_cannot_create_holiday(
    client: TestClient, member_token: str
) -> None:
    r = client.post(
        "/api/v1/admin/holidays",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"date": "2026-05-03", "name": "test", "type": "national"},
    )
    assert r.status_code == 403


# ---------- Closings ----------
def test_close_blocks_new_punches(
    client: TestClient,
    admin_token: str,
    member_token: str,
    member: Employee,
    db_session: Session,
) -> None:
    # Give member an April 2026 punch so there's something to close
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_IN,
        punched_at=_jst(2026, 4, 20, 9, 0),
    )
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_OUT,
        punched_at=_jst(2026, 4, 20, 18, 0),
    )
    db_session.commit()

    # Close April
    r = client.post(
        f"/api/v1/admin/closings/close?year=2026&month=4&employee_id={member.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["closed"] == 1

    # Additional punch for April should now fail 409
    r2 = client.post(
        "/api/v1/attendance/punches",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"type": "clock_in"},
    )
    # Current punch is "today", likely not April — so it's OK. Test the
    # service-layer block directly for the closed month instead.
    # Instead: try recording a punch into April directly in service.
    try:
        attendance_service.record_punch(
            db_session,
            employee_id=member.id,
            punch_type=PunchType.CLOCK_IN,
            punched_at=_jst(2026, 4, 21, 9, 0),
        )
        raise AssertionError("should have raised PunchError(month_closed)")
    except attendance_service.PunchError as exc:
        assert str(exc) == "month_closed"


def test_close_all_and_status(
    client: TestClient, admin_token: str, member: Employee
) -> None:
    h = {"Authorization": f"Bearer {admin_token}"}
    # close all for May 2026 (no data, still creates closing rows for all active)
    r = client.post(
        "/api/v1/admin/closings/close?year=2026&month=5", headers=h
    )
    assert r.status_code == 200
    # Status returns all active employees with closed=true
    r2 = client.get(
        "/api/v1/admin/closings/status?year=2026&month=5", headers=h
    )
    assert r2.status_code == 200
    rows = r2.json()["rows"]
    assert len(rows) >= 2  # admin + member
    assert all(row["closed"] for row in rows)


def test_reopen_allows_punch_again(
    client: TestClient,
    admin_token: str,
    member: Employee,
    db_session: Session,
) -> None:
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_IN,
        punched_at=_jst(2026, 4, 20, 9, 0),
    )
    db_session.commit()
    client.post(
        f"/api/v1/admin/closings/close?year=2026&month=4&employee_id={member.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Reopen
    r = client.post(
        f"/api/v1/admin/closings/reopen?year=2026&month=4&employee_id={member.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200

    # service-level punch should now succeed
    attendance_service.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_OUT,
        punched_at=_jst(2026, 4, 20, 18, 0),
    )
    db_session.commit()
    closing = closing_service.get_closing(
        db_session, employee_id=member.id, year=2026, month=4
    )
    assert closing is not None
    assert closing.closed_at is None


# ---------- CSV exports ----------
def test_export_monthly_csv_headers(
    client: TestClient, admin_token: str
) -> None:
    r = client.get(
        "/api/v1/admin/exports/monthly.csv?year=2026&month=4",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    text = r.text
    # BOM present
    assert text.startswith("\ufeff")
    first_line = text.splitlines()[0]
    assert "employee_id" in first_line
    assert "worked_minutes" in first_line


def test_export_leaves_csv(
    client: TestClient, admin_token: str
) -> None:
    r = client.get(
        "/api/v1/admin/exports/leaves.csv?year=2026",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "granted_days" in r.text.splitlines()[0]


def test_member_cannot_export(client: TestClient, member_token: str) -> None:
    r = client.get(
        "/api/v1/admin/exports/monthly.csv?year=2026&month=4",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r.status_code == 403
