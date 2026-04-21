from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.employee import Employee
from app.models.users_session import UsersSession


def test_login_success_and_me(client: TestClient, admin: Employee) -> None:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "AdminPass1!"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == admin.email
    assert me.json()["role"] == "admin"


def test_login_wrong_password(client: TestClient, admin: Employee) -> None:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "nope"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "invalid_credentials"


def test_login_inactive_user(
    client: TestClient, admin: Employee, db_session: Session
) -> None:
    admin.active = False
    db_session.merge(admin)
    db_session.commit()

    res = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "AdminPass1!"},
    )
    assert res.status_code == 401


def test_me_without_token(client: TestClient) -> None:
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["detail"] == "missing_token"


def test_refresh_rotation_and_reuse_rejected(
    client: TestClient, admin: Employee
) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "AdminPass1!"},
    ).json()
    old_refresh = login["refresh_token"]

    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    new = rotated.json()
    assert new["refresh_token"] != old_refresh

    reused = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401


def test_logout_revokes_refresh(
    client: TestClient, admin: Employee, db_session: Session
) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "AdminPass1!"},
    ).json()

    res = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {login['access_token']}"},
        json={"refresh_token": login["refresh_token"]},
    )
    assert res.status_code == 204

    sessions = db_session.execute(select(UsersSession)).scalars().all()
    assert all(s.revoked_at is not None for s in sessions)

    reused = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert reused.status_code == 401


def test_login_records_audit(
    client: TestClient, admin: Employee, db_session: Session
) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "AdminPass1!"},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "wrong"},
    )
    logs = db_session.execute(select(AuditLog)).scalars().all()
    actions = {log.action for log in logs}
    assert "auth.login_success" in actions
    assert "auth.login_failed" in actions
