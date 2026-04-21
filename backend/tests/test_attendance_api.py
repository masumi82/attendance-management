from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient


def test_punch_flow_today(client: TestClient, member_token: str) -> None:
    headers = {"Authorization": f"Bearer {member_token}"}

    # today 初期状態
    r = client.get("/api/v1/attendance/today", headers=headers)
    assert r.status_code == 200
    assert r.json()["state"] == "none"
    assert r.json()["daily"] is None

    # clock_in
    r = client.post(
        "/api/v1/attendance/punches",
        headers=headers,
        json={"type": "clock_in"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["type"] == "clock_in"

    # today は working
    r = client.get("/api/v1/attendance/today", headers=headers)
    assert r.json()["state"] == "working"
    assert r.json()["daily"]["status"] == "pending"

    # 重複 clock_in で 409
    r = client.post(
        "/api/v1/attendance/punches",
        headers=headers,
        json={"type": "clock_in"},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "already_clocked_in"


def test_monthly_rollup(client: TestClient, member_token: str) -> None:
    today = datetime.now(UTC)
    # 当月の API が空でも 200 で stats=0
    r = client.get(
        "/api/v1/attendance/monthly",
        headers={"Authorization": f"Bearer {member_token}"},
        params={"year": today.year, "month": today.month},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == today.year
    assert body["month"] == today.month
    assert body["stats"]["working_days"] == 0


def test_admin_can_view_other_employees_today(
    client: TestClient, admin_token: str, member_token: str
) -> None:
    # member が clock_in
    client.post(
        "/api/v1/attendance/punches",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"type": "clock_in"},
    )
    # member_token 利用者の ID を /me から取る
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {member_token}"},
    ).json()

    # admin が他社員の today を参照できる
    r = client.get(
        "/api/v1/attendance/today",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"employee_id": me["id"]},
    )
    assert r.status_code == 200
    assert r.json()["state"] == "working"


def test_member_cannot_view_others_today(
    client: TestClient, admin_token: str, member_token: str
) -> None:
    admin_me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    r = client.get(
        "/api/v1/attendance/today",
        headers={"Authorization": f"Bearer {member_token}"},
        params={"employee_id": admin_me["id"]},
    )
    assert r.status_code == 403
