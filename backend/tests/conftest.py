from __future__ import annotations

import os

# Must be set BEFORE app imports so Settings cache picks it up
os.environ["APP_ENV"] = "test"

from collections.abc import Iterator  # noqa: E402

from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user  # noqa: F401, E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.employee import Employee, Role  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _verify_db_reachable() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


@pytest.fixture()
def db_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_db() -> Iterator[None]:
    """Truncate all mutable tables between tests (preserves schema)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE "
                "audit_logs, users_sessions, revoked_access_tokens, "
                "approvals, requests, "
                "overtime_alerts, leave_balances, monthly_closings, "
                "daily_attendance, attendance_punches, shifts, holidays, "
                "employees, departments RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def admin(db_session: Session) -> Employee:
    user = Employee(
        email="admin@example.com",
        hashed_password=hash_password("AdminPass1!"),
        name="管理者",
        role=Role.ADMIN,
        active=True,
        hire_date=date(2020, 4, 1),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def approver(db_session: Session) -> Employee:
    user = Employee(
        email="approver@example.com",
        hashed_password=hash_password("ApproverPass1!"),
        name="承認者",
        role=Role.APPROVER,
        active=True,
        hire_date=date(2020, 4, 1),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def approver_token(client: TestClient, approver: Employee) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": approver.email, "password": "ApproverPass1!"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture()
def member(db_session: Session) -> Employee:
    user = Employee(
        email="member@example.com",
        hashed_password=hash_password("MemberPass1!"),
        name="一般社員",
        role=Role.MEMBER,
        active=True,
        hire_date=date(2020, 4, 1),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_token(client: TestClient, admin: Employee) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "AdminPass1!"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture()
def member_token(client: TestClient, member: Employee) -> str:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": member.email, "password": "MemberPass1!"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]
