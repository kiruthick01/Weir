"""Connect deterministic policy, the proposal agent, state, and the ledger."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, select

from . import governance_agent, policy_engine
from .db import ApprovalRequestModel, ApproverModel, DecisionModel, RequestClassModel, add_decision

logger = logging.getLogger(__name__)


class _AgentDb:
    def __init__(self, session: Any):
        self.session = session

    def get_request(self, request_id: str):
        return self.session.get(ApprovalRequestModel, request_id)

    def get_request_class(self, name: str):
        return self.session.get(RequestClassModel, name)

    def get_backup_approvers(self, approver_id: str):
        approver = self.session.get(ApproverModel, approver_id)
        backup = self.session.get(ApproverModel, approver.backup_approver_id) if approver and approver.backup_approver_id else None
        return [backup] if backup else []

    def get_recent_decisions(self, approver_id: str, limit: int = 10):
        return list(self.session.scalars(select(DecisionModel).where(DecisionModel.approver_id == approver_id).order_by(DecisionModel.created_at.desc()).limit(limit)))

    def get_policy(self, name: str):
        return self.get_request_class(name)

    def count_auto_approved(self, approver_id: str, since: datetime):
        return self.session.scalar(select(func.count(DecisionModel.id)).where(DecisionModel.approver_id == approver_id, DecisionModel.outcome == "auto_approved", DecisionModel.created_at >= since)) or 0


class _LedgerState:
    def __init__(self, state_store: Any, db_session: Any):
        self._state_store = state_store
        self._db = _AgentDb(db_session)

    def __getattr__(self, name: str):
        return getattr(self._state_store, name)

    def count_auto_approved(self, approver_id: str, since: datetime):
        return self._db.count_auto_approved(approver_id, since)


def _request_class(model: RequestClassModel) -> policy_engine.RequestClass:
    return policy_engine.RequestClass(model.max_wait_seconds, model.risk_tier, model.auto_approve_threshold)


def _request(model: ApprovalRequestModel) -> policy_engine.ApprovalRequest:
    return policy_engine.ApprovalRequest(model.id, model.approver_id, model.payload or {}, model.submitted_at)


def _policy_config(settings: Any) -> policy_engine.PolicyConfig:
    return policy_engine.PolicyConfig(auto_approve_rate_limit_per_hour=getattr(settings, "auto_approve_rate_limit_per_hour", 10))


async def _commit_proposal(proposal, request, request_class, approver, session, wrapped_store, settings):
    validation = await policy_engine.validate_proposal(proposal, request, request_class, approver, wrapped_store, _policy_config(settings))
    if not validation.ok:
        add_decision(session, request.request_id, approver.approver_id, "rejected_proposal", validation.reason, proposal.reason)
        return False
    outcomes = {"propose_delegate": "delegated", "propose_auto_approve": "auto_approved", "propose_escalate_to_human": "queued", "propose_hold": "hold"}
    outcome = outcomes[proposal.kind]
    reason = proposal.reason if proposal.kind != "propose_escalate_to_human" else f"escalated_to_human: {proposal.reason}"
    add_decision(session, request.request_id, approver.approver_id, outcome, reason, proposal.reason)
    request_model = session.get(ApprovalRequestModel, request.request_id)
    if request_model:
        request_model.status = outcome
        session.commit()
    return True


async def handle_pressure_transition(approver_id: str, db_session: Any, state_store: Any, mode: str) -> None:
    """Run one agent pass, validate every proposal, retry each rejection once, and fail open."""
    try:
        agent_db = _AgentDb(db_session)
        wrapped_store = _LedgerState(state_store, db_session)
        settings = getattr(db_session, "settings", SimpleNamespace())
        proposals, degraded = await governance_agent.run_governance_agent(approver_id, agent_db, wrapped_store, mode)
        if degraded:
            logger.error("governance agent unavailable, failing open")

        approver_model = db_session.get(ApproverModel, approver_id)
        if not approver_model:
            return
        approver = policy_engine.Approver(approver_model.id, approver_model.backup_approver_id)

        for proposal in proposals:
            request_model = db_session.get(ApprovalRequestModel, proposal.request_id)
            if not request_model:
                continue
            request_class_model = db_session.get(RequestClassModel, request_model.request_class_name)
            request = _request(request_model)
            request_class = _request_class(request_class_model)
            validation = await policy_engine.validate_proposal(proposal, request, request_class, approver, wrapped_store, _policy_config(settings))
            if validation.ok:
                await _commit_proposal(proposal, request, request_class, approver, db_session, wrapped_store, settings)
                continue
            add_decision(db_session, request.request_id, approver.approver_id, "rejected_proposal", validation.reason, proposal.reason)
            fallback = await governance_agent.retry_rejected_proposal(proposal, validation.reason, {"request_id": request.request_id, "payload": request.payload, "request_class": request_class_model.name}, mode)
            if fallback is not None:
                await _commit_proposal(fallback, request, request_class, approver, db_session, wrapped_store, settings)

        now = datetime.now(timezone.utc)
        for request_id in await state_store.timed_out_requests(approver_id, now):
            request_model = db_session.get(ApprovalRequestModel, request_id)
            if request_model and request_model.status not in {"approved", "auto_approved", "delegated", "timed_out"}:
                add_decision(db_session, request_id, approver_id, "timed_out", "request deadline exceeded")
                request_model.status = "timed_out"
                db_session.commit()
                await state_store.dequeue(approver_id, request_id)
    except Exception:
        logger.exception("governance agent unavailable, failing open")
