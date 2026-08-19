"""The deterministic, auditable policy state machine for Weir."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol


PRESSURE_ORDER = {"normal": 0, "elevated": 1, "critical": 2}


@dataclass(frozen=True, slots=True)
class PressureThresholds:
    """Latency thresholds and hysteresis settings for one policy."""

    threshold_elevated_ms: int
    threshold_critical_ms: int
    consecutive_samples: int = 1
    hysteresis_pct: float = 10.0


@dataclass(frozen=True, slots=True)
class PressureState:
    state: str
    p50_ms: int | None
    transitioned: bool
    last_transition_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RequestClass:
    max_wait_seconds: int
    risk_tier: str
    auto_approve_threshold: float | int | None = None


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    critical_trigger_pct: float = 0.50
    auto_approve_rate_limit_per_hour: int = 10
    allow_medium_risk_auto_approve: bool = False


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    request_id: str
    approver_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    submitted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True, slots=True)
class Approver:
    approver_id: str
    backup_approver_id: str | None = None


@dataclass(frozen=True, slots=True)
class Action:
    kind: str
    request_id: str
    deadline: datetime | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class Proposal:
    kind: str
    request_id: str
    target_approver_id: str | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    reason: str


class StateStoreProtocol(Protocol):
    async def get_latency_p50(self, approver_id: str) -> int | None: ...

    async def get_pressure_state(
        self, approver_id: str
    ) -> tuple[str, datetime] | None: ...

    async def set_pressure_state(
        self, approver_id: str, state: str, now: datetime
    ) -> bool: ...

    async def queue_depth(self, approver_id: str) -> int: ...

    async def timed_out_requests(
        self, approver_id: str, now: datetime
    ) -> list[str]: ...


# Consecutive pressure observations are policy-engine state, not request state.
# The store identity keeps independent StateStore instances isolated in tests
# and in applications that create more than one policy context.
_consecutive_observations: dict[tuple[int, str, str], int] = {}


def _target_pressure(
    p50_ms: int | None,
    thresholds: PressureThresholds,
    current_state: str,
    consecutive_count: int,
) -> str:
    if p50_ms is None:
        return "normal"

    required = max(1, thresholds.consecutive_samples)
    elevated_up = p50_ms > thresholds.threshold_elevated_ms
    critical_up = p50_ms > thresholds.threshold_critical_ms

    if current_state == "critical":
        critical_down = thresholds.threshold_critical_ms * (
            1 - thresholds.hysteresis_pct / 100
        )
        if p50_ms <= critical_down:
            return "elevated" if consecutive_count >= required else "critical"
        return "critical"

    if current_state == "elevated":
        elevated_down = thresholds.threshold_elevated_ms * (
            1 - thresholds.hysteresis_pct / 100
        )
        if not elevated_up and p50_ms <= elevated_down:
            return "normal"
        if critical_up and consecutive_count >= required:
            return "critical"
        return "elevated"

    if critical_up and consecutive_count >= required:
        return "critical"
    if elevated_up and consecutive_count >= required:
        return "elevated"
    return "normal"


async def evaluate_pressure(
    approver_id: str,
    state_store: StateStoreProtocol,
    thresholds: PressureThresholds,
) -> PressureState:
    """Evaluate p50 latency, apply hysteresis, and persist pressure state."""
    if thresholds.threshold_critical_ms < thresholds.threshold_elevated_ms:
        raise ValueError("critical threshold must be >= elevated threshold")
    if thresholds.consecutive_samples < 1:
        raise ValueError("consecutive_samples must be at least 1")
    if not 0 <= thresholds.hysteresis_pct < 100:
        raise ValueError("hysteresis_pct must be between 0 and 100")

    now = datetime.now(timezone.utc)
    p50_ms = await state_store.get_latency_p50(approver_id)
    stored = await state_store.get_pressure_state(approver_id)
    current_state = stored[0] if stored is not None else "normal"

    if p50_ms is None:
        observation_key = (id(state_store), approver_id, "none")
        _consecutive_observations[observation_key] = 0
    elif p50_ms > thresholds.threshold_critical_ms:
        observation_key = (id(state_store), approver_id, "critical")
        _consecutive_observations[observation_key] = (
            _consecutive_observations.get(observation_key, 0) + 1
        )
    elif p50_ms > thresholds.threshold_elevated_ms:
        observation_key = (id(state_store), approver_id, "elevated")
        _consecutive_observations[observation_key] = (
            _consecutive_observations.get(observation_key, 0) + 1
        )
    else:
        observation_key = (id(state_store), approver_id, "normal")
        _consecutive_observations[observation_key] = (
            _consecutive_observations.get(observation_key, 0) + 1
        )

    # A new metric band starts a fresh consecutive run.
    for key in list(_consecutive_observations):
        if key[0] == id(state_store) and key[1] == approver_id and key != observation_key:
            _consecutive_observations[key] = 0

    target = _target_pressure(
        p50_ms,
        thresholds,
        current_state,
        _consecutive_observations[observation_key],
    )
    changed = await state_store.set_pressure_state(approver_id, target, now)
    actual = await state_store.get_pressure_state(approver_id)

    return PressureState(
        state=actual[0] if actual is not None else target,
        p50_ms=p50_ms,
        transitioned=changed,
        last_transition_at=actual[1] if actual is not None else None,
    )


def _request_value(request: Any) -> float | int | None:
    payload = getattr(request, "payload", None)
    if payload is None and isinstance(request, dict):
        payload = request.get("payload", {})
    if not isinstance(payload, dict):
        return None
    return payload.get("amount", payload.get("value"))


def _request_field(request: Any, name: str, default: Any = None) -> Any:
    if isinstance(request, dict):
        return request.get(name, default)
    return getattr(request, name, default)


async def select_action(
    request: ApprovalRequest,
    request_class: RequestClass,
    pressure_state: PressureState,
    state_store: StateStoreProtocol,
    policy_config: PolicyConfig,
) -> Action:
    """Select only deterministic admission actions; agents decide proposals."""
    now = datetime.now(timezone.utc)
    request_id = _request_field(request, "request_id")
    approver_id = _request_field(request, "approver_id")

    if request_id in await state_store.timed_out_requests(approver_id, now):
        return Action("timed_out", request_id, reason="request deadline exceeded")

    deadline = now + timedelta(seconds=request_class.max_wait_seconds)
    depth = await state_store.queue_depth(approver_id)

    if pressure_state.state == "critical":
        submitted_at = _request_field(request, "submitted_at", now)
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=timezone.utc)
        waited = (now - submitted_at).total_seconds()
        trigger = request_class.max_wait_seconds * policy_config.critical_trigger_pct
        if waited >= trigger:
            return Action(
                "eligible_for_agent_review",
                request_id,
                deadline=deadline,
                reason="critical pressure and critical wait threshold reached",
            )

    if depth > 0:
        return Action("queue", request_id, deadline=deadline, reason="approver backlog exists")

    return Action("pass", request_id, deadline=deadline, reason="capacity available")


async def _auto_approved_count(
    state_store: Any,
    approver_id: str,
    since: datetime,
) -> int:
    counter = getattr(state_store, "count_auto_approved", None)
    if counter is None:
        counter = getattr(state_store, "auto_approved_count", None)
    if counter is None:
        raise AttributeError(
            "state_store must expose count_auto_approved(approver_id, since)"
        )
    result = counter(approver_id, since)
    if hasattr(result, "__await__"):
        result = await result
    return int(result)


async def validate_proposal(
    proposal: Proposal,
    request: ApprovalRequest,
    request_class: RequestClass,
    approver: Approver,
    state_store: StateStoreProtocol,
    policy_config: PolicyConfig,
) -> ValidationResult:
    """Validate an agent proposal, returning the first hard-limit failure."""
    if proposal.request_id != _request_field(request, "request_id"):
        return ValidationResult(False, "proposal request_id does not match request")

    if proposal.kind == "propose_auto_approve":
        allowed_risks = {"low"}
        if policy_config.allow_medium_risk_auto_approve:
            allowed_risks.add("medium")
        if request_class.risk_tier not in allowed_risks:
            return ValidationResult(False, "auto-approval is not allowed for this risk tier")

        threshold = request_class.auto_approve_threshold
        value = _request_value(request)
        if threshold is None:
            return ValidationResult(False, "auto-approval is disabled for this request class")
        if value is None:
            return ValidationResult(False, "request has no numeric value for auto-approval")
        if value > threshold:
            return ValidationResult(False, "request value exceeds auto-approval threshold")

        since = datetime.now(timezone.utc) - timedelta(hours=1)
        count = await _auto_approved_count(
            state_store,
            approver.approver_id,
            since,
        )
        if count >= policy_config.auto_approve_rate_limit_per_hour:
            return ValidationResult(False, "auto-approval hourly rate limit exceeded")

        return ValidationResult(True, "auto-approval proposal satisfies policy limits")

    if proposal.kind == "propose_delegate":
        if proposal.target_approver_id != approver.backup_approver_id:
            return ValidationResult(False, "delegation target is not the approver's backup")
        return ValidationResult(True, "delegation target is the configured backup approver")

    if proposal.kind in {"propose_escalate_to_human", "propose_hold"}:
        return ValidationResult(True, f"{proposal.kind} requires no additional hard-limit check")

    return ValidationResult(False, f"unknown proposal kind: {proposal.kind}")

