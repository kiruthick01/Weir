from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import ApprovalRequestModel, ApproverModel
from .deps import get_db

router = APIRouter(prefix="/v1/approvers", tags=["approvers"])


@router.get("")
def list_approvers(db: Session = Depends(get_db)):
    return {"approvers": [{"approver_id": item.id, "name": item.name, "email": item.email} for item in db.scalars(select(ApproverModel).order_by(ApproverModel.name))]}


@router.get("/{approver_id}/status")
async def approver_status(approver_id: str, request: Request, db: Session = Depends(get_db)):
    approver = db.get(ApproverModel, approver_id)
    if not approver:
        raise HTTPException(404, "approver not found")
    state = await request.app.state.state_store.get_pressure_state(approver_id)
    return {"approver_id": approver_id, "pressure_state": state[0] if state else "normal", "latency_p50_ms": await request.app.state.state_store.get_latency_p50(approver_id), "queue_depth": await request.app.state.state_store.queue_depth(approver_id), "state_since": state[1] if state else None}


@router.get("/{approver_id}/queue")
async def approver_queue(approver_id: str, request: Request, db: Session = Depends(get_db)):
    if not db.get(ApproverModel, approver_id):
        raise HTTPException(404, "approver not found")
    rows = []
    for item in await request.app.state.state_store.queue_snapshot(approver_id):
        record = db.get(ApprovalRequestModel, item["request_id"])
        rows.append({"request_id": item["request_id"], "deadline": item["deadline"], "source_system": record.source_system if record else "unknown", "request_class": record.request_class_name if record else "unknown", "submitted_at": record.submitted_at if record else None})
    return {"approver_id": approver_id, "queue": rows}
