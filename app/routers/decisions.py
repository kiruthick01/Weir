from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import ApprovalRequestModel, ApproverModel, DecisionModel, add_decision
from .deps import get_db

router = APIRouter(prefix="/v1/decisions", tags=["decisions"])


class OverrideBody(BaseModel):
    action: str
    target_approver_id: str | None = None
    reason: str


def require_admin(request: Request, key: str | None):
    if not key or key != request.app.state.settings.admin_api_key:
        raise HTTPException(401, "invalid admin key")


@router.get("/recent")
def recent(limit: int = 50, offset: int = 0, approver_id: str | None = None, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    statement = select(DecisionModel).order_by(DecisionModel.created_at.desc()).offset(offset).limit(limit)
    if approver_id:
        statement = statement.where(DecisionModel.approver_id == approver_id)
    items = [{"id": d.id, "request_id": d.request_id, "approver_id": d.approver_id, "outcome": d.outcome, "reason": d.reason, "agent_reasoning": d.agent_reasoning, "created_at": d.created_at} for d in db.scalars(statement)]
    return {"items": items, "limit": limit, "offset": offset, "next_offset": offset + limit if len(items) == limit else None}


@router.post("/{request_id}/override")
def override(request_id: str, body: OverrideBody, request: Request, x_admin_key: str | None = Header(None), db: Session = Depends(get_db)):
    require_admin(request, x_admin_key)
    record = db.get(ApprovalRequestModel, request_id)
    if not record:
        raise HTTPException(404, "request not found")
    if body.action not in {"force_approve", "force_reassign"}:
        raise HTTPException(422, "action must be force_approve or force_reassign")
    if body.action == "force_reassign":
        if not body.target_approver_id or not db.get(ApproverModel, body.target_approver_id):
            raise HTTPException(404, "target approver not found")
        record.approver_id = body.target_approver_id
        outcome = "delegated"
    else:
        outcome = "manually_approved"
    record.status = outcome
    decision = add_decision(db, request_id, record.approver_id, outcome, f"manual_override: {body.reason}")
    return {"request_id": request_id, "outcome": decision.outcome}
