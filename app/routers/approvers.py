from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import ApproverModel
from .deps import get_db

router = APIRouter(prefix="/v1/approvers", tags=["approvers"])


@router.get("/{approver_id}/status")
async def approver_status(approver_id: str, request: Request, db: Session = Depends(get_db)):
    approver = db.get(ApproverModel, approver_id)
    if not approver:
        raise HTTPException(404, "approver not found")
    state = await request.app.state.state_store.get_pressure_state(approver_id)
    return {"approver_id": approver_id, "pressure_state": state[0] if state else "normal", "latency_p50_ms": await request.app.state.state_store.get_latency_p50(approver_id), "queue_depth": await request.app.state.state_store.queue_depth(approver_id), "state_since": state[1] if state else None}
