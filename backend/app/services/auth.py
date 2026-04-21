from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    decode_token,
    generate_refresh_token,
    hash_password,
    issue_access_token,
    needs_rehash,
    refresh_token_ttl,
    verify_password,
)
from app.models.employee import Employee
from app.models.revoked_access_token import RevokedAccessToken
from app.models.users_session import UsersSession


class AuthError(Exception):
    """Generic authentication error."""


def _hash_refresh(raw: str) -> str:
    pepper = get_settings().REFRESH_TOKEN_PEPPER
    payload = f"{pepper}:{raw}" if pepper else raw
    return hashlib.sha256(payload.encode()).hexdigest()


def authenticate(db: Session, *, email: str, password: str) -> Employee:
    stmt = select(Employee).where(Employee.email == email.lower())
    user = db.execute(stmt).scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthError("invalid_credentials")
    if not user.active:
        raise AuthError("user_disabled")
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(password)
    return user


def issue_token_pair(
    db: Session,
    *,
    user: Employee,
    request: Request | None = None,
) -> tuple[str, str, datetime, str]:
    """Return (access_token, refresh_token, access_expires_at, access_jti)."""
    access_token, expires_at, jti = issue_access_token(
        subject=user.id, role=user.role.value
    )

    raw_refresh = generate_refresh_token()
    session = UsersSession(
        employee_id=user.id,
        refresh_token_hash=_hash_refresh(raw_refresh),
        user_agent=(request.headers.get("user-agent") if request else None),
        ip_address=_extract_ip(request),
        expires_at=datetime.now(UTC) + refresh_token_ttl(),
    )
    db.add(session)
    db.flush()
    return access_token, raw_refresh, expires_at, jti


def rotate_refresh(
    db: Session,
    *,
    refresh_token: str,
    request: Request | None = None,
) -> tuple[Employee, str, str, datetime, str]:
    token_hash = _hash_refresh(refresh_token)
    stmt = select(UsersSession).where(UsersSession.refresh_token_hash == token_hash)
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        raise AuthError("invalid_refresh")
    # Reuse detection: a revoked refresh token is being presented again.
    # Treat as compromise and revoke all active sessions for the owner.
    # Commit the revocations before raising so the caller's `db.rollback()`
    # in the error path does not undo the lockout.
    if session.revoked_at is not None:
        revoke_all_for_user(db, employee_id=session.employee_id)
        db.commit()
        raise AuthError("refresh_reused")
    if session.expires_at <= datetime.now(UTC):
        raise AuthError("refresh_expired")

    user = db.get(Employee, session.employee_id)
    if user is None or not user.active:
        raise AuthError("user_disabled")

    # Rotation: revoke old, issue new
    session.revoked_at = datetime.now(UTC)
    access_token, raw_refresh, expires_at, jti = issue_token_pair(
        db, user=user, request=request
    )
    return user, access_token, raw_refresh, expires_at, jti


def revoke_refresh(db: Session, *, refresh_token: str) -> bool:
    token_hash = _hash_refresh(refresh_token)
    stmt = select(UsersSession).where(UsersSession.refresh_token_hash == token_hash)
    session = db.execute(stmt).scalar_one_or_none()
    if session is None or session.revoked_at is not None:
        return False
    session.revoked_at = datetime.now(UTC)
    return True


def revoke_access_jti(
    db: Session, *, jti: str, expires_at: datetime, reason: str = "logout"
) -> None:
    """Add the given access-token JTI to the denylist.

    Idempotent: if already present, this is a no-op.
    """
    existing = db.get(RevokedAccessToken, jti)
    if existing is not None:
        return
    db.add(
        RevokedAccessToken(
            jti=jti,
            expires_at=expires_at,
            reason=reason,
        )
    )
    db.flush()


def is_access_jti_revoked(db: Session, *, jti: str) -> bool:
    return db.get(RevokedAccessToken, jti) is not None


def revoke_all_for_user(db: Session, *, employee_id: UUID) -> int:
    stmt = select(UsersSession).where(
        UsersSession.employee_id == employee_id,
        UsersSession.revoked_at.is_(None),
    )
    sessions = db.execute(stmt).scalars().all()
    now = datetime.now(UTC)
    for s in sessions:
        s.revoked_at = now
    return len(sessions)


def _extract_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    if fwd := request.headers.get("x-forwarded-for"):
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


__all__ = [
    "AuthError",
    "authenticate",
    "decode_token",
    "is_access_jti_revoked",
    "issue_token_pair",
    "revoke_access_jti",
    "revoke_all_for_user",
    "revoke_refresh",
    "rotate_refresh",
]
