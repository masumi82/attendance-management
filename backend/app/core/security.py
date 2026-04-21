from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import get_settings

_ph = PasswordHasher()

TokenType = Literal["access", "refresh"]


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        _ph.verify(hashed, raw)
    except VerifyMismatchError:
        return False
    return True


def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _issue_token(
    *,
    subject: str | UUID,
    token_type: TokenType,
    expires_delta: timedelta,
    extra: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "type": token_type,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def issue_access_token(
    *, subject: str | UUID, role: str
) -> tuple[str, datetime, str]:
    """Issue an access token and return (token, expires_at, jti)."""
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRES_MINUTES)
    jti = uuid.uuid4().hex
    token = _issue_token(
        subject=subject,
        token_type="access",
        expires_delta=expires_delta,
        extra={"role": role, "jti": jti},
    )
    expires_at = datetime.now(UTC) + expires_delta
    return token, expires_at, jti


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError("invalid_token") from exc
    if payload.get("type") != expected_type:
        raise ValueError("token_type_mismatch")
    return payload


def refresh_token_ttl() -> timedelta:
    settings = get_settings()
    return timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRES_DAYS)
