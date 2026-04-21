from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.employee import Employee
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    TokenPair,
)
from app.services import audit, auth as auth_service

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
@limiter.limit(lambda: get_settings().RATE_LIMIT_LOGIN)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user = auth_service.authenticate(db, email=payload.email, password=payload.password)
    except auth_service.AuthError as exc:
        audit.record_audit(
            db,
            actor_id=None,
            action="auth.login_failed",
            target_type="email",
            target_id=payload.email.lower(),
            diff={"reason": [None, str(exc)]},
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        ) from None

    access_token, refresh_token, expires_at, _jti = auth_service.issue_token_pair(
        db, user=user, request=request
    )
    audit.record_audit(
        db,
        actor_id=user.id,
        action="auth.login_success",
        target_type="employee",
        target_id=user.id,
        request=request,
    )
    db.commit()
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )


@router.post("/refresh", response_model=TokenPair)
@limiter.limit(lambda: get_settings().RATE_LIMIT_REFRESH)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    try:
        user, access_token, refresh_token, expires_at, _jti = auth_service.rotate_refresh(
            db, refresh_token=payload.refresh_token, request=request
        )
    except auth_service.AuthError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from None

    audit.record_audit(
        db,
        actor_id=user.id,
        action="auth.refresh",
        target_type="employee",
        target_id=user.id,
        request=request,
    )
    db.commit()
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> None:
    auth_service.revoke_refresh(db, refresh_token=payload.refresh_token)
    # Revoke the access token currently presented so it cannot be reused
    # before its natural expiry. The access payload is attached to
    # request.state by get_current_user.
    access_payload = getattr(request.state, "access_payload", None)
    if access_payload:
        jti = access_payload.get("jti")
        exp = access_payload.get("exp")
        if jti and exp:
            auth_service.revoke_access_jti(
                db,
                jti=jti,
                expires_at=datetime.fromtimestamp(int(exp), tz=UTC),
                reason="logout",
            )
    audit.record_audit(
        db,
        actor_id=current.id,
        action="auth.logout",
        target_type="employee",
        target_id=current.id,
        request=request,
    )
    db.commit()


@router.get("/me", response_model=MeResponse)
def me(current: Employee = Depends(get_current_user)) -> Employee:
    return current


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> None:
    if not verify_password(payload.current_password, current.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_current_password",
        )
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="new_password_same_as_current",
        )
    current.hashed_password = hash_password(payload.new_password)
    # Kill all other refresh sessions so other devices must re-login
    auth_service.revoke_all_for_user(db, employee_id=current.id)
    audit.record_audit(
        db,
        actor_id=current.id,
        action="auth.change_password",
        target_type="employee",
        target_id=current.id,
        request=request,
    )
    db.commit()
