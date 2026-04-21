"""Regression tests for the security-hardening PR.

Covers:
  - C2: rate limit on /auth/login
  - H1: CSV formula injection sanitizer
  - M1: insufficient-balance error surface is generic (no remaining/requested leak)
  - M2: audit_logs append-only (UPDATE/DELETE raise)
  - M6: purge of expired revoked_access_tokens
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.closings import _sanitize_cell
from app.models.audit_log import AuditLog
from app.models.employee import Employee
from app.models.revoked_access_token import RevokedAccessToken
from app.services import leaves as leave_service


# ---------------------------------------------------------------------------
# H1: CSV formula injection
# ---------------------------------------------------------------------------
def test_h1_csv_sanitize_prefixes_dangerous_chars() -> None:
    for dangerous in ["=SUM(A1)", "+cmd", "-10", "@SUM", "\tleading-tab", "\rCR"]:
        out = _sanitize_cell(dangerous)
        assert out.startswith("'"), f"not escaped: {dangerous!r} -> {out!r}"


def test_h1_csv_sanitize_leaves_safe_cells_alone() -> None:
    for safe in ["Alice", "admin@example.com", "2026-04-21", "9:00", "", "0"]:
        assert _sanitize_cell(safe) == safe


def test_h1_csv_sanitize_none_becomes_empty() -> None:
    assert _sanitize_cell(None) == ""


# ---------------------------------------------------------------------------
# M1: error surface
# ---------------------------------------------------------------------------
def test_m1_insufficient_balance_error_code_is_generic(
    db_session: Session, member: Employee
) -> None:
    # no grant — deduct 1 day fails
    try:
        leave_service.deduct_leave(
            db_session,
            employee_id=member.id,
            year=2026,
            days=__import__("decimal").Decimal("1"),
        )
        raise AssertionError("should have raised")
    except leave_service.LeaveError as exc:
        # No remaining=/requested= leak.
        assert str(exc) == "insufficient_balance"


# ---------------------------------------------------------------------------
# M2: audit_logs append-only
# ---------------------------------------------------------------------------
def test_m2_audit_logs_insert_is_allowed_but_update_raises(
    db_session: Session, admin: Employee
) -> None:
    row = AuditLog(actor_id=admin.id, action="test.append_only")
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    # UPDATE must raise
    try:
        db_session.execute(
            text("UPDATE audit_logs SET action='tampered' WHERE id=:i"),
            {"i": row.id},
        )
        db_session.commit()
        raise AssertionError("UPDATE on audit_logs should have raised")
    except Exception as exc:
        db_session.rollback()
        assert "append-only" in str(exc) or "not permitted" in str(exc)


def test_m2_audit_logs_delete_raises(
    db_session: Session, admin: Employee
) -> None:
    row = AuditLog(actor_id=admin.id, action="test.append_only_delete")
    db_session.add(row)
    db_session.commit()
    try:
        db_session.execute(
            text("DELETE FROM audit_logs WHERE id=:i"), {"i": row.id}
        )
        db_session.commit()
        raise AssertionError("DELETE on audit_logs should have raised")
    except Exception as exc:
        db_session.rollback()
        assert "append-only" in str(exc) or "not permitted" in str(exc)


# ---------------------------------------------------------------------------
# M6: purge expired revoked_access_tokens
# ---------------------------------------------------------------------------
def test_m6_purge_expired_revoked_tokens(db_session: Session) -> None:
    now = datetime.now(UTC)
    db_session.add_all([
        RevokedAccessToken(
            jti="expired_jti_1",
            expires_at=now - timedelta(hours=1),
            reason="logout",
        ),
        RevokedAccessToken(
            jti="expired_jti_2",
            expires_at=now - timedelta(days=30),
            reason="logout",
        ),
        RevokedAccessToken(
            jti="still_valid_jti",
            expires_at=now + timedelta(hours=1),
            reason="logout",
        ),
    ])
    db_session.commit()

    from app.jobs.scheduler import _run_purge_revoked_access_tokens

    _run_purge_revoked_access_tokens()

    # Reset view since purge ran in its own session
    db_session.expire_all()
    remaining = [
        r.jti
        for r in db_session.query(RevokedAccessToken).all()
    ]
    assert "still_valid_jti" in remaining
    assert "expired_jti_1" not in remaining
    assert "expired_jti_2" not in remaining


# ---------------------------------------------------------------------------
# C2: rate limit on /auth/login
# ---------------------------------------------------------------------------
def test_c2_login_rate_limit_eventually_returns_429(
    client: TestClient, admin: Employee, monkeypatch
) -> None:
    # The limiter is disabled under APP_ENV=test (see core.rate_limit). We
    # temporarily re-enable it for this single assertion. Also tighten the
    # limit via env so the test is fast and deterministic.
    from app.core import config as config_module

    monkeypatch.setenv("RATE_LIMIT_LOGIN", "3/minute")
    config_module.get_settings.cache_clear()

    from app.core.rate_limit import limiter

    limiter.reset()
    limiter.enabled = True

    url = "/api/v1/auth/login"
    body = {"email": admin.email, "password": "AdminPass1!"}

    try:
        got_429 = False
        for _ in range(10):
            res = client.post(url, json=body)
            if res.status_code == 429:
                got_429 = True
                break
        assert got_429, "rate limiter did not trigger 429"
    finally:
        limiter.enabled = False
        limiter.reset()
        config_module.get_settings.cache_clear()
