from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import orchestrator, policy_engine
from ..db import ApprovalRequestModel, ApproverModel, RequestClassModel, add_decision
from ..policy_engine import PressureThresholds
from .deps import get_db

router = APIRouter(prefix="/v1/requests", tags=["requests"])


class RequestBody(BaseModel):
    source_system: str
    external_ref: str
    request_class: str
    approver_email: str
    payload: dict = Field(default_factory=dict)


@router.post("")
async def create_request(body: RequestBody, request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    request_class = db.get(RequestClassModel, body.request_class)
    approver = db.scalar(select(ApproverModel).where(ApproverModel.email == body.approver_email))
    if not request_class or not approver:
        raise HTTPException(404, "request_class or approver_email not found")

    existing = db.scalar(select(ApprovalRequestModel).where(ApprovalRequestModel.source_system == body.source_system, ApprovalRequestModel.external_ref == body.external_ref))
    if existing:
        pressure = await request.app.state.state_store.get_pressure_state(existing.approver_id)
        return {"request_id": existing.id, "status": existing.status, "pressure_state": pressure[0] if pressure else "normal", "estimated_wait_seconds": None}

    now = datetime.now(timezone.utc)
    record = ApprovalRequestModel(source_system=body.source_system, external_ref=body.external_ref, request_class_name=body.request_class, approver_id=approver.id, payload=body.payload, status="queued", submitted_at=now)
    db.add(record)
    db.commit()
    db.refresh(record)

    settings = request.app.state.settings
    thresholds = PressureThresholds(settings.threshold_elevated_ms, settings.threshold_critical_ms, settings.policy_state_consecutive_samples, settings.policy_state_hysteresis_pct)
    pressure = await policy_engine.evaluate_pressure(approver.id, request.app.state.state_store, thresholds)
    if pressure.transitioned and pressure.state in {"elevated", "critical"}:
        background_tasks.add_task(_background_transition, request.app.state, approver.id)

    request_class_policy = policy_engine.RequestClass(request_class.max_wait_seconds, request_class.risk_tier, request_class.auto_approve_threshold)
    action = await policy_engine.select_action(policy_engine.ApprovalRequest(record.id, approver.id, body.payload, now), request_class_policy, pressure, request.app.state.state_store, policy_engine.PolicyConfig())
    deadline = action.deadline or (now + timedelta(seconds=request_class.max_wait_seconds))
    await request.app.state.state_store.enqueue(approver.id, record.id, deadline)
    add_decision(db, record.id, approver.id, "queued", f"policy_action: {action.kind}")
    # Simple, conservative estimate: time until this request's deadline.
    estimated = max(0, int((deadline - now).total_seconds()))
    return {"request_id": record.id, "status": "queued", "pressure_state": pressure.state, "estimated_wait_seconds": estimated}


async def _background_transition(app_state, approver_id: str):
    session = app_state.session_factory()
    try:
        await orchestrator.handle_pressure_transition(approver_id, session, app_state.state_store, app_state.settings.agent_mode)
    finally:
        session.close()

