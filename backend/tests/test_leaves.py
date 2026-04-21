from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.services import leaves as leave_service


def test_compute_grant_days() -> None:
    # under 6 months => 0
    assert leave_service.compute_annual_grant_days(
        date(2026, 1, 1), at=date(2026, 4, 1)
    ) == Decimal("0")
    # 6 months exact => 10
    assert leave_service.compute_annual_grant_days(
        date(2025, 10, 1), at=date(2026, 4, 1)
    ) == Decimal("10")
    # 3 years service => 13
    assert leave_service.compute_annual_grant_days(
        date(2023, 4, 1), at=date(2026, 4, 1)
    ) == Decimal("13")
    # cap at 20
    assert leave_service.compute_annual_grant_days(
        date(2000, 4, 1), at=date(2026, 4, 1)
    ) == Decimal("20")


def test_grant_and_summary(db_session: Session, member: Employee) -> None:
    leave_service.grant_annual_leave(db_session, employee=member, year=2026)
    db_session.commit()
    summary = leave_service.get_summary(db_session, employee=member, year=2026)
    # hire_date=2020-04-01, so 6 years service -> 16 days (but capped 20)
    assert summary.granted_days == Decimal("16")
    assert summary.used_days == Decimal("0")
    assert summary.remaining_days == Decimal("16")


def test_deduct_full_day(db_session: Session, member: Employee) -> None:
    leave_service.grant_annual_leave(db_session, employee=member, year=2026)
    leave_service.deduct_leave(
        db_session, employee_id=member.id, year=2026, days=Decimal("1.0")
    )
    db_session.commit()
    s = leave_service.get_summary(db_session, employee=member, year=2026)
    assert s.used_days == Decimal("1.0")
    assert s.remaining_days == Decimal("15.0")


def test_deduct_half_day(db_session: Session, member: Employee) -> None:
    leave_service.grant_annual_leave(db_session, employee=member, year=2026)
    leave_service.deduct_leave(
        db_session, employee_id=member.id, year=2026, days=Decimal("0.5")
    )
    db_session.commit()
    s = leave_service.get_summary(db_session, employee=member, year=2026)
    assert s.used_days == Decimal("0.5")


def test_insufficient_balance(db_session: Session, member: Employee) -> None:
    leave_service.grant_annual_leave(db_session, employee=member, year=2026)
    # 16 days granted, try to use 17
    try:
        leave_service.deduct_leave(
            db_session,
            employee_id=member.id,
            year=2026,
            days=Decimal("17.0"),
        )
        raise AssertionError("should have raised")
    except leave_service.LeaveError as exc:
        assert "insufficient_balance" in str(exc)


def test_carry_over(db_session: Session, member: Employee) -> None:
    leave_service.grant_annual_leave(db_session, employee=member, year=2026)
    leave_service.deduct_leave(
        db_session, employee_id=member.id, year=2026, days=Decimal("4.0")
    )
    moved = leave_service.carry_over(db_session, from_year=2026)
    db_session.commit()
    assert moved == 1
    nxt = leave_service.get_summary(db_session, employee=member, year=2027)
    assert nxt.carried_over_days == Decimal("12.0")
    assert nxt.remaining_days == Decimal("12.0")


def test_approve_leave_deducts_balance(
    client: TestClient,
    member_token: str,
    approver_token: str,
    db_session: Session,
    member: Employee,
) -> None:
    # Grant balance
    leave_service.grant_annual_leave(db_session, employee=member, year=2026)
    db_session.commit()

    # Create a leave request (full_day, 2 days)
    created = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "payload": {
                "kind": "leave",
                "start_date": "2026-04-22",
                "end_date": "2026-04-23",
                "leave_kind": "full_day",
                "reason": "家族旅行",
            }
        },
    ).json()

    # Approver takes it
    queue = client.get(
        "/api/v1/approvals/queue",
        headers={"Authorization": f"Bearer {approver_token}"},
    ).json()
    target = next(item for item in queue if item["request"]["id"] == created["id"])
    r = client.post(
        f"/api/v1/approvals/{target['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"comment": "OK"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "approved"

    s = leave_service.get_summary(db_session, employee=member, year=2026)
    assert s.used_days == Decimal("2.0")
    assert s.remaining_days == Decimal("14.0")


def test_approve_leave_insufficient_balance_fails(
    client: TestClient,
    member_token: str,
    approver_token: str,
) -> None:
    # No grant => granted_days = 0
    created = client.post(
        "/api/v1/requests",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "payload": {
                "kind": "leave",
                "start_date": "2026-04-22",
                "end_date": "2026-04-22",
                "leave_kind": "full_day",
                "reason": "私用",
            }
        },
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
    assert r.status_code == 409
    assert "insufficient" in r.json()["detail"]


def test_balance_api_own_and_admin(
    client: TestClient,
    admin_token: str,
    member_token: str,
    db_session: Session,
    member: Employee,
) -> None:
    leave_service.grant_annual_leave(db_session, employee=member, year=2026)
    db_session.commit()

    # member can see own balance
    r = client.get(
        "/api/v1/leaves/balance?year=2026",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2026
    assert float(body["remaining_days"]) == 16.0

    # admin can list all balances
    r2 = client.get(
        "/api/v1/admin/leaves/balances?year=2026",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert any(row["employee_email"] == member.email for row in body2["rows"])

    # member cannot list all
    r3 = client.get(
        "/api/v1/admin/leaves/balances?year=2026",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert r3.status_code == 403


def test_admin_grant_all(
    client: TestClient, admin_token: str, member: Employee
) -> None:
    r = client.post(
        "/api/v1/admin/leaves/grant-all",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"year": 2026},
    )
    assert r.status_code == 200
    assert r.json()["year"] == 2026
    assert r.json()["granted_for_employees"] >= 2  # admin + member at least
