"""Weir's proposal-only governance agent.

The caller should invoke this module after a pressure transition into
``elevated`` or ``critical`` and may invoke it again every 30--60 seconds
while that pressure is sustained.  This module observes state and proposes
actions; it never writes decisions, changes queues, or mutates approval state.

``run_governance_agent`` returns ``(proposals, degraded)``.  A degraded live
call returns an empty proposal list and ``degraded=True`` so the caller can
record the fail-open event and continue its deterministic workflow.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .policy_engine import ApprovalRequest, Proposal


logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
LIVE_TIMEOUT_SECONDS = 8
MAX_REASONING_PASSES = 3


READ_TOOL_SCHEMAS = [
    {
        "name": "get_approver_pressure",
        "description": "Read the current pressure and latency signal for an approver.",
        "input_schema": {
            "type": "object",
            "properties": {"approver_id": {"type": "string"}},
            "required": ["approver_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_queue_state",
        "description": "Read the complete queued-request context for an approver.",
        "input_schema": {
            "type": "object",
            "properties": {"approver_id": {"type": "string"}},
            "required": ["approver_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_backup_approvers",
        "description": "Read configured backup approvers and their pressure states.",
        "input_schema": {
            "type": "object",
            "properties": {"approver_id": {"type": "string"}},
            "required": ["approver_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_policy",
        "description": "Read the policy settings for a request class.",
        "input_schema": {
            "type": "object",
            "properties": {"request_class_name": {"type": "string"}},
            "required": ["request_class_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_recent_decisions",
        "description": "Read recent ledger decisions for an approver.",
        "input_schema": {
            "type": "object",
            "properties": {
                "approver_id": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            },
            "required": ["approver_id"],
            "additionalProperties": False,
        },
    },
]

PROPOSE_TOOL_SCHEMAS = [
    {
        "name": "propose_delegate",
        "description": "Propose delegation to the requester's legal backup approver.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "target_approver_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["request_id", "target_approver_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_auto_approve",
        "description": "Propose automatic approval of a low-risk request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["request_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_escalate_to_human",
        "description": "Propose escalation to a human decision-maker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["request_id", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "propose_hold",
        "description": "Explicitly propose taking no action on a request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["request_id", "reason"],
            "additionalProperties": False,
        },
    },
]

CLAUDE_TOOL_SCHEMAS = READ_TOOL_SCHEMAS + PROPOSE_TOOL_SCHEMAS


def propose_delegate(request_id: str, target_approver_id: str, reason: str) -> Proposal:
    return Proposal("propose_delegate", request_id, target_approver_id, reason)


def propose_auto_approve(request_id: str, reason: str) -> Proposal:
    return Proposal("propose_auto_approve", request_id, None, reason)


def propose_escalate_to_human(request_id: str, reason: str) -> Proposal:
    return Proposal("propose_escalate_to_human", request_id, None, reason)


def propose_hold(request_id: str, reason: str) -> Proposal:
    return Proposal("propose_hold", request_id, None, reason)


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


async def _call_db(db_session: Any, names: tuple[str, ...], *args: Any, default: Any) -> Any:
    for name in names:
        function = getattr(db_session, name, None)
        if function is None:
            continue
        result = function(*args)
        if hasattr(result, "__await__"):
            result = await result
        return result
    return default


async def get_approver_pressure(
    approver_id: str, state_store: Any, db_session: Any = None
) -> dict[str, Any]:
    current = await state_store.get_pressure_state(approver_id)
    return {
        "approver_id": approver_id,
        "state": current[0] if current else "normal",
        "latency_p50_ms": await state_store.get_latency_p50(approver_id),
        "since": current[1].isoformat() if current else None,
    }


async def get_queue_state(
    approver_id: str, state_store: Any, db_session: Any
) -> list[dict[str, Any]]:
    snapshot = await state_store.queue_snapshot(approver_id)
    now = datetime.now(timezone.utc)
    result: list[dict[str, Any]] = []
    for item in snapshot:
        request_id = item["request_id"]
        request = await _call_db(db_session, ("get_request", "find_request"), request_id, default={})
        request_class_name = _value(request, "request_class_name", _value(request, "request_class", "unknown"))
        request_class = await _call_db(
            db_session,
            ("get_request_class", "find_request_class"),
            request_class_name,
            default={},
        )
        deadline = item["deadline"]
        result.append(
            {
                "request_id": request_id,
                "request_class": request_class_name,
                "policy": request_class,
                "payload_summary": _value(request, "payload", {}),
                "enqueue_time": _value(request, "submitted_at", _value(request, "enqueued_at")),
                "deadline": deadline.isoformat() if isinstance(deadline, datetime) else deadline,
                "time_until_deadline_seconds": (deadline - now).total_seconds() if isinstance(deadline, datetime) else None,
            }
        )
    return result


async def get_backup_approvers(
    approver_id: str, state_store: Any, db_session: Any
) -> list[dict[str, Any]]:
    backups = await _call_db(
        db_session,
        ("get_backup_approvers", "find_backup_approvers"),
        approver_id,
        default=[],
    )
    result = []
    for backup in backups or []:
        backup_id = _value(backup, "approver_id", _value(backup, "id"))
        pressure = await get_approver_pressure(backup_id, state_store)
        result.append({"approver_id": backup_id, "name": _value(backup, "name"), "pressure": pressure})
    return result


async def get_policy(request_class_name: str, db_session: Any) -> dict[str, Any]:
    return await _call_db(
        db_session,
        ("get_policy", "get_request_class", "find_request_class"),
        request_class_name,
        default={},
    )


async def get_recent_decisions(
    approver_id: str, db_session: Any, limit: int = 10
) -> list[Any]:
    return await _call_db(
        db_session,
        ("get_recent_decisions", "recent_decisions"),
        approver_id,
        limit,
        default=[],
    )


async def _build_context(approver_id: str, db_session: Any, state_store: Any) -> dict[str, Any]:
    pressure, queue, backups, recent = await asyncio.gather(
        get_approver_pressure(approver_id, state_store, db_session),
        get_queue_state(approver_id, state_store, db_session),
        get_backup_approvers(approver_id, state_store, db_session),
        get_recent_decisions(approver_id, db_session),
    )
    policies = {}
    for item in queue:
        class_name = item["request_class"]
        if class_name not in policies:
            policies[class_name] = await get_policy(class_name, db_session)
    return {"approver_pressure": pressure, "queue": queue, "backup_approvers": backups, "policies": policies, "recent_decisions": recent}


def _offline_proposals(context: dict[str, Any]) -> list[Proposal]:
    backups = context["backup_approvers"]
    backup = next((item for item in backups if item["pressure"]["state"] != "critical"), None)
    proposals = []
    for item in context["queue"]:
        policy = item.get("policy") or context["policies"].get(item["request_class"], {})
        max_wait = _value(policy, "max_wait_seconds")
        waited_fraction = None
        if max_wait and item.get("enqueue_time"):
            enqueue_time = item["enqueue_time"]
            if isinstance(enqueue_time, str):
                enqueue_time = datetime.fromisoformat(enqueue_time)
            if isinstance(enqueue_time, datetime) and enqueue_time.tzinfo is None:
                enqueue_time = enqueue_time.replace(tzinfo=timezone.utc)
            waited_fraction = (datetime.now(timezone.utc) - enqueue_time).total_seconds() / max_wait
        if waited_fraction is None or waited_fraction < 0.50:
            continue
        amount = (item.get("payload_summary") or {}).get("amount")
        threshold = _value(policy, "auto_approve_threshold")
        if threshold is not None and amount is not None and amount <= threshold:
            proposals.append(propose_auto_approve(item["request_id"], "offline policy: low-value request past critical wait trigger"))
        elif backup is not None:
            proposals.append(propose_delegate(item["request_id"], backup["approver_id"], "offline policy: backup is not critical"))
        else:
            proposals.append(propose_escalate_to_human(item["request_id"], "offline policy: no safe backup is available"))
    return proposals


def _proposal_from_tool(name: str, data: dict[str, Any]) -> Proposal | None:
    functions: dict[str, Callable[..., Proposal]] = {
        "propose_delegate": propose_delegate,
        "propose_auto_approve": propose_auto_approve,
        "propose_escalate_to_human": propose_escalate_to_human,
        "propose_hold": propose_hold,
    }
    function = functions.get(name)
    if function is None:
        return None
    return function(**data)


async def _live_call(context: dict[str, Any], db_session: Any, state_store: Any) -> list[Proposal]:
    import anthropic

    client = anthropic.Anthropic()
    messages: list[dict[str, Any]] = [{"role": "user", "content": json.dumps(context, default=str)}]
    proposals: list[Proposal] = []
    for _ in range(MAX_REASONING_PASSES):
        response = await asyncio.to_thread(
            client.messages.create,
            model=MODEL,
            max_tokens=1200,
            system="""You are Weir Governance Agent. Analyze the complete approver context. You may propose actions only. Never claim to have executed an action. Use proposal tools for every recommendation, and only propose safe, explainable actions.""",
            tools=CLAUDE_TOOL_SCHEMAS,
            messages=messages,
        )
        tool_uses = [block for block in response.content if getattr(block, "type", None) == "tool_use"]
        if not tool_uses:
            break
        tool_results = []
        for block in tool_uses:
            data = block.input or {}
            proposal = _proposal_from_tool(block.name, data)
            if proposal is not None:
                proposals.append(proposal)
                result = {"accepted_as_proposal": True, "proposal": proposal.__dict__ if hasattr(proposal, "__dict__") else {"kind": proposal.kind, "request_id": proposal.request_id}}
            else:
                result = await _execute_read_tool(block.name, data, db_session, state_store)
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, default=str)})
        messages.extend([{"role": "assistant", "content": response.content}, {"role": "user", "content": tool_results}])
    return proposals


async def _execute_read_tool(name: str, data: dict[str, Any], db_session: Any, state_store: Any) -> Any:
    if name == "get_approver_pressure":
        return await get_approver_pressure(data["approver_id"], state_store, db_session)
    if name == "get_queue_state":
        return await get_queue_state(data["approver_id"], state_store, db_session)
    if name == "get_backup_approvers":
        return await get_backup_approvers(data["approver_id"], state_store, db_session)
    if name == "get_policy":
        return await get_policy(data["request_class_name"], db_session)
    if name == "get_recent_decisions":
        return await get_recent_decisions(data["approver_id"], db_session, data.get("limit", 10))
    return {"error": f"unknown tool: {name}"}


async def run_governance_agent(
    approver_id: str,
    db_session: Any,
    state_store: Any,
    mode: str,
) -> tuple[list[Proposal], bool]:
    """Run one batched governance pass; return proposals and degraded flag."""
    try:
        context = await _build_context(approver_id, db_session, state_store)
        if mode == "offline":
            return _offline_proposals(context), False
        if mode != "live":
            raise ValueError("mode must be 'live' or 'offline'")
        return await asyncio.wait_for(_live_call(context, db_session, state_store), LIVE_TIMEOUT_SECONDS), False
    except Exception:
        if mode == "live":
            logger.exception("governance agent unavailable")
            return [], True
        raise


async def retry_rejected_proposal(
    original_proposal: Proposal,
    rejection_reason: str,
    request_context: dict[str, Any],
    mode: str,
) -> Proposal | None:
    """Request one constrained fallback proposal after policy rejection."""
    request_id = original_proposal.request_id
    if mode == "offline":
        reason = rejection_reason.lower()
        if "rate limit" in reason:
            return propose_hold(request_id, "retry fallback: auto-approval rate limit reached")
        if any(word in reason for word in ("risk", "value", "threshold", "disabled")):
            return propose_escalate_to_human(request_id, f"retry fallback after rejection: {rejection_reason}")
        return propose_hold(request_id, f"retry fallback after rejection: {rejection_reason}")

    async def live_retry() -> Proposal | None:
        import anthropic

        client = anthropic.Anthropic()
        response = await asyncio.to_thread(
            client.messages.create,
            model=MODEL,
            max_tokens=500,
            system="You are Weir Governance Agent. Produce exactly one safe fallback proposal using a proposal tool. Do not repeat the rejected action.",
            tools=PROPOSE_TOOL_SCHEMAS,
            messages=[{"role": "user", "content": json.dumps({"request": request_context, "rejected_proposal": original_proposal.__dict__ if hasattr(original_proposal, "__dict__") else {"kind": original_proposal.kind, "request_id": request_id}, "rejection_reason": rejection_reason}, default=str)}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use":
                proposal = _proposal_from_tool(block.name, block.input or {})
                if proposal is not None and proposal.kind != original_proposal.kind:
                    return proposal
        return None

    try:
        return await asyncio.wait_for(live_retry(), LIVE_TIMEOUT_SECONDS)
    except Exception:
        logger.exception("governance agent unavailable")
        return None
