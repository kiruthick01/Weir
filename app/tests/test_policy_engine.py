from datetime import datetime, timedelta, timezone

import pytest

from app.policy_engine import (
    ApprovalRequest,
    Approver,
    PolicyConfig,
    PressureThresholds,
    Proposal,
    RequestClass,
    evaluate_pressure,
    validate_proposal,
)
from app.state_store import StateStore


async def record(store: StateStore, approver_id: str, latency: int) -> None:
    for _ in range(2):
        await store.record_decision_latency(approver_id, latency)


@pytest.mark.asyncio
async def test_pressure_ramp_and_hysteresis():
    store = StateStore(policy_state_cooldown_seconds=0)
    thresholds = PressureThresholds(100, 200, consecutive_samples=2, hysteresis_pct=20)

    await record(store, "a", 150)
    first = await evaluate_pressure("a", store, thresholds)
    assert first.state == "normal"
    second = await evaluate_pressure("a", store, thresholds)
    assert second.state == "elevated"

    for _ in range(4):
        await store.record_decision_latency("a", 250)
    assert (await evaluate_pressure("a", store, thresholds)).state == "elevated"
    assert (await evaluate_pressure("a", store, thresholds)).state == "critical"

    for _ in range(5):
        await store.record_decision_latency("a", 150)
    good_sample = await evaluate_pressure("a", store, thresholds)
    assert good_sample.state == "critical"


@pytest.mark.asyncio
async def test_auto_approve_rejects_value_threshold():
    store = StateStore()
    store.count_auto_approved = lambda approver_id, since: 0
    request = ApprovalRequest("r1", "a", {"amount": 101})
    result = await validate_proposal(
        Proposal("propose_auto_approve", "r1"),
        request,
        RequestClass(60, "low", auto_approve_threshold=100),
        Approver("a", "backup"),
        store,
        PolicyConfig(),
    )
    assert not result.ok
    assert "threshold" in result.reason


@pytest.mark.asyncio
async def test_delegate_must_target_backup():
    result = await validate_proposal(
        Proposal("propose_delegate", "r1", target_approver_id="other"),
        ApprovalRequest("r1", "a"),
        RequestClass(60, "medium"),
        Approver("a", "backup"),
        StateStore(),
        PolicyConfig(),
    )
    assert not result.ok
    assert "backup" in result.reason


@pytest.mark.asyncio
async def test_pressure_upgrade_bypasses_cooldown_but_downgrade_waits():
    # A long cooldown (60s default) must never delay recognizing worsening
    # pressure -- including an approver's very first evaluation, which
    # always writes an implicit "normal" baseline and must not accidentally
    # arm a cooldown that then blocks the first real transition. Recovering
    # (downgrading) is exactly the direction that should wait out the
    # cooldown, so a brief good sample right after a spike doesn't cause
    # flapping back to normal.
    store = StateStore(policy_state_cooldown_seconds=60)
    thresholds = PressureThresholds(100, 200, consecutive_samples=1, hysteresis_pct=20)

    await store.record_decision_latency("a", 250)
    first = await evaluate_pressure("a", store, thresholds)
    assert first.state == "critical"  # upgraded immediately, no cooldown wait

    await store.record_decision_latency("a", 10)
    still_critical = await evaluate_pressure("a", store, thresholds)
    assert still_critical.state == "critical"  # downgrade blocked by cooldown


@pytest.mark.asyncio
async def test_auto_approve_rate_limit():
    store = StateStore()
    store.count_auto_approved = lambda approver_id, since: 2
    result = await validate_proposal(
        Proposal("propose_auto_approve", "r1"),
        ApprovalRequest("r1", "a", {"amount": 10}),
        RequestClass(60, "low", auto_approve_threshold=100),
        Approver("a", "backup"),
        store,
        PolicyConfig(auto_approve_rate_limit_per_hour=2),
    )
    assert not result.ok
    assert "rate limit" in result.reason
