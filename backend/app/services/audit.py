from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def record_audit(
    db: Session,
    *,
    actor_id: UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: str | UUID | None = None,
    diff: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        diff=diff,
        ip_address=_client_ip(request) if request else None,
        user_agent=_user_agent(request) if request else None,
    )
    db.add(entry)
    db.flush()
    return entry


def _client_ip(request: Request) -> str | None:
    if fwd := request.headers.get("x-forwarded-for"):
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:255] if ua else None
