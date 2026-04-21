from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.employee import Employee, Role
from app.models.revoked_access_token import RevokedAccessToken

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Employee:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    # Denylist check: reject tokens whose JTI has been revoked (e.g., logout).
    jti = payload.get("jti")
    if jti and db.get(RevokedAccessToken, jti) is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_subject") from None
    user = db.get(Employee, user_id)
    if user is None or not user.active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user_disabled")
    request.state.current_user = user
    request.state.access_payload = payload
    return user


def require_role(*allowed: Role) -> Callable[[Employee], Employee]:
    allowed_set = set(allowed)

    def _checker(current: Employee = Depends(get_current_user)) -> Employee:
        if current.role not in allowed_set:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return current

    return _checker


def require_admin(current: Employee = Depends(get_current_user)) -> Employee:
    if current.role != Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_only")
    return current
