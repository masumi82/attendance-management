from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_employees_requires_admin(
    client: TestClient, member_token: str
) -> None:
    res = client.get(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert res.status_code == 403
    assert res.json()["detail"] == "admin_only"


def test_list_employees_as_admin(client: TestClient, admin_token: str) -> None:
    res = client.get(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    assert any(e["role"] == "admin" for e in body)


def test_create_employee(client: TestClient, admin_token: str) -> None:
    res = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "new@example.com",
            "password": "Welcome123!",
            "name": "新入社員",
            "role": "member",
        },
    )
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["email"] == "new@example.com"
    assert created["role"] == "member"

    # duplicate
    again = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "new@example.com",
            "password": "Welcome123!",
            "name": "重複",
            "role": "member",
        },
    )
    assert again.status_code == 409


def test_update_employee_role(
    client: TestClient, admin_token: str
) -> None:
    created = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "promote@example.com",
            "password": "Welcome123!",
            "name": "昇格候補",
            "role": "member",
        },
    ).json()

    res = client.patch(
        f"/api/v1/employees/{created['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "approver"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "approver"


def test_create_employee_forbidden_for_member(
    client: TestClient, member_token: str
) -> None:
    res = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "email": "whatever@example.com",
            "password": "Welcome123!",
            "name": "x",
            "role": "member",
        },
    )
    assert res.status_code == 403
