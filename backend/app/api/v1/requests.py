from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request as HttpRequest, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.employee import Employee, Role
from app.schemas.request import (
    ApprovalOut,
    ApprovalQueueItem,
    DecisionRequest,
    RequestCreate,
    RequestDetail,
    RequestOut,
)
from app.services import audit, requests as req_service

router = APIRouter(prefix="/v1/requests", tags=["requests"])
approvals_router = APIRouter(prefix="/v1/approvals", tags=["approvals"])


@router.post("", response_model=RequestDetail, status_code=status.HTTP_201_CREATED)
def create_request(
    payload: RequestCreate,
    http_request: HttpRequest,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> RequestDetail:
    req = req_service.create_request(db, employee=current, payload=payload)
    audit.record_audit(
        db,
        actor_id=current.id,
        action=f"request.create.{req.type.value}",
        target_type="request",
        target_id=req.id,
        diff={"status": [None, req.status.value]},
        request=http_request,
    )
    db.commit()

    detail = req_service.get_request_with_approvals(db, request_id=req.id)
    assert detail is not None
    req, approvals = detail
    return RequestDetail(
        **RequestOut.model_validate(req).model_dump(),
        approvals=[ApprovalOut.model_validate(a) for a in approvals],
    )


@router.get("", response_model=list[RequestOut])
def list_requests(
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> list[RequestOut]:
    reqs = req_service.list_own_requests(db, employee_id=current.id)
    return [RequestOut.model_validate(r) for r in reqs]


@router.get("/{request_id}", response_model=RequestDetail)
def get_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> RequestDetail:
    pair = req_service.get_request_with_approvals(db, request_id=request_id)
    if pair is None:
        raise HTTPException(status_code=404, detail="request_not_found")
    req, approvals = pair
    if req.employee_id != current.id and current.role not in (Role.ADMIN, Role.APPROVER):
        raise HTTPException(status_code=403, detail="forbidden")
    return RequestDetail(
        **RequestOut.model_validate(req).model_dump(),
        approvals=[ApprovalOut.model_validate(a) for a in approvals],
    )


@router.post("/{request_id}/cancel", response_model=RequestOut)
def cancel_request(
    request_id: UUID,
    http_request: HttpRequest,
    db: Session = Depends(get_db),
    current: Employee = Depends(get_current_user),
) -> RequestOut:
    pair = req_service.get_request_with_approvals(db, request_id=request_id)
    if pair is None:
        raise HTTPException(status_code=404, detail="request_not_found")
    req_obj, _ = pair
    try:
        updated = req_service.cancel_request(db, request_obj=req_obj, current=current)
    except req_service.RequestError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    audit.record_audit(
        db,
        actor_id=current.id,
        action="request.cancel",
        target_type="request",
        target_id=updated.id,
        diff={"status": ["pending", "canceled"]},
        request=http_request,
    )
    db.commit()
    db.refresh(updated)
    return RequestOut.model_validate(updated)


# ---------------- approvals queue & decisions ----------------

@approvals_router.get("/queue", response_model=list[ApprovalQueueItem])
def queue(
    db: Session = Depends(get_db),
    _approver: Employee = Depends(require_role(Role.APPROVER, Role.ADMIN)),
) -> list[ApprovalQueueItem]:
    rows = req_service.approval_queue(db)
    items: list[ApprovalQueueItem] = []
    for approval, request_obj, requester in rows:
        items.append(
            ApprovalQueueItem(
                approval_id=approval.id,
                request=RequestOut.model_validate(request_obj),
                step=approval.step,
                requested_by_name=requester.name,
                requested_by_email=requester.email,
            )
        )
    return items


@approvals_router.post("/{approval_id}/approve", response_model=RequestDetail)
def approve(
    approval_id: UUID,
    body: DecisionRequest,
    http_request: HttpRequest,
    db: Session = Depends(get_db),
    approver: Employee = Depends(require_role(Role.APPROVER, Role.ADMIN)),
) -> RequestDetail:
    return _decide(
        db,
        approval_id=approval_id,
        decision="approved",
        comment=body.comment,
        approver=approver,
        http_request=http_request,
    )


@approvals_router.post("/{approval_id}/reject", response_model=RequestDetail)
def reject(
    approval_id: UUID,
    body: DecisionRequest,
    http_request: HttpRequest,
    db: Session = Depends(get_db),
    approver: Employee = Depends(require_role(Role.APPROVER, Role.ADMIN)),
) -> RequestDetail:
    return _decide(
        db,
        approval_id=approval_id,
        decision="rejected",
        comment=body.comment,
        approver=approver,
        http_request=http_request,
    )


def _decide(
    db: Session,
    *,
    approval_id: UUID,
    decision: str,
    comment: str | None,
    approver: Employee,
    http_request: HttpRequest,
) -> RequestDetail:
    from app.models.request import Approval

    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="approval_not_found")

    try:
        req, approval = req_service.decide(
            db,
            approval=approval,
            decision=decision,
            approver=approver,
            comment=comment,
        )
    except req_service.RequestError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from None

    audit.record_audit(
        db,
        actor_id=approver.id,
        action=f"request.{decision}",
        target_type="request",
        target_id=req.id,
        diff={"status": ["pending", decision]},
        request=http_request,
    )
    db.commit()

    pair = req_service.get_request_with_approvals(db, request_id=req.id)
    assert pair is not None
    req, approvals = pair
    return RequestDetail(
        **RequestOut.model_validate(req).model_dump(),
        approvals=[ApprovalOut.model_validate(a) for a in approvals],
    )
