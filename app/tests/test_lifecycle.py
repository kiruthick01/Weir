"""Integration coverage for the request lifecycle end to end.

These exercise the full FastAPI app (not just the isolated policy engine)
because the bugs this file guards against were all in the *wiring* between
routers, the orchestrator, and the state store: a terminal decision that
never left the live queue, and a delegation that never actually moved the
request to its new approver.
"""

from __future__ import annotations

import os
import uuid

os.environ.setdefault("WEIR_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WEIR_AGENT_MODE", "offline")

import pytest
from fastapi.testclient import TestClient

from app.db import ApproverModel, RequestClassModel
from main import app


def _seeded_client(tmp_path, monkeypatch, name, **env):
    db_path = tmp_path / f"{name}.db"
    monkeypatch.setenv("WEIR_DATABASE_URL", f"sqlite:///{db_path}")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    test_client = TestClient(app)
    test_client.__enter__()
    session = app.state.session_factory()
    alice = ApproverModel(email="alice@example.com", name="Alice")
    bob = ApproverModel(email="bob@example.com", name="Bob")
    session.add(alice)
    session.add(bob)
    session.commit()
    session.refresh(alice)
    session.refresh(bob)
    alice.backup_approver_id = bob.id
    session.add(RequestClassModel(name="low", max_wait_seconds=300, auto_approve_threshold=1000, risk_tier="low"))
    session.commit()
    test_client.alice_id = alice.id
    test_client.bob_id = bob.id
    session.close()
    return test_client


@pytest.fixture()
def client(tmp_path, monkeypatch):
    test_client = _seeded_client(tmp_path, monkeypatch, "lifecycle")
    yield test_client
    test_client.__exit__(None, None, None)


@pytest.fixture()
def fast_pressure_client(tmp_path, monkeypatch):
    # Tiny thresholds so the backlog-age test only needs a handful of short
    # real sleeps instead of racing the (deliberately demo-sized) defaults.
    test_client = _seeded_client(
        tmp_path,
        monkeypatch,
        "fast-pressure",
        WEIR_THRESHOLD_ELEVATED_MS="40",
        WEIR_THRESHOLD_CRITICAL_MS="120",
        POLICY_STATE_CONSECUTIVE_SAMPLES="2",
    )
    yield test_client
    test_client.__exit__(None, None, None)


def _submit(client, n=1, approver_email="alice@example.com"):
    ids = []
    for _ in range(n):
        response = client.post(
            "/v1/requests",
            json={
                "source_system": "test",
                # uuid4, not id(object()): a tight loop can have CPython
                # reuse the same freed address for each throwaway object,
                # which silently collapses these into duplicate external_ref
                # values and makes every call after the first hit the
                # idempotent-existing-request short circuit instead of
                # actually creating a new request.
                "external_ref": f"ref-{approver_email}-{uuid.uuid4()}",
                "request_class": "low",
                "approver_email": approver_email,
                "payload": {"amount": 50},
            },
        )
        assert response.status_code == 200, response.text
        ids.append(response.json()["request_id"])
    return ids


def test_force_approve_removes_request_from_live_queue(client):
    request_ids = _submit(client, n=3)
    before = client.get(f"/v1/approvers/{client.alice_id}/queue").json()
    assert len(before["queue"]) == 3

    response = client.post(
        f"/v1/decisions/{request_ids[0]}/override",
        json={"action": "force_approve", "reason": "test"},
        headers={"X-Admin-Key": "dev-admin-key"},
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "manually_approved"

    after = client.get(f"/v1/approvers/{client.alice_id}/queue").json()
    assert len(after["queue"]) == 2
    assert request_ids[0] not in {row["request_id"] for row in after["queue"]}


def test_force_reassign_moves_request_to_target_approver(client):
    request_ids = _submit(client, n=2)

    response = client.post(
        f"/v1/decisions/{request_ids[0]}/override",
        json={"action": "force_reassign", "target_approver_id": client.bob_id, "reason": "overloaded"},
        headers={"X-Admin-Key": "dev-admin-key"},
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "delegated"

    alice_queue = client.get(f"/v1/approvers/{client.alice_id}/queue").json()["queue"]
    bob_queue = client.get(f"/v1/approvers/{client.bob_id}/queue").json()["queue"]
    assert request_ids[0] not in {row["request_id"] for row in alice_queue}
    assert request_ids[0] in {row["request_id"] for row in bob_queue}


def test_override_rejects_already_resolved_request(client):
    request_ids = _submit(client, n=1)
    first = client.post(
        f"/v1/decisions/{request_ids[0]}/override",
        json={"action": "force_approve", "reason": "test"},
        headers={"X-Admin-Key": "dev-admin-key"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/v1/decisions/{request_ids[0]}/override",
        json={"action": "force_approve", "reason": "duplicate click"},
        headers={"X-Admin-Key": "dev-admin-key"},
    )
    assert second.status_code == 409


def test_backlog_ages_and_lifts_pressure_off_normal(fast_pressure_client):
    # No requests are ever decided here (mirrors --ramp mode in
    # scripts/simulate_requests.py), so the only way pressure can move off
    # "normal" is the backlog-age signal recorded in routers/requests.py:
    # each new arrival samples how long the oldest still-queued item has
    # been waiting. Real elapsed time is required for that, so this sleeps
    # briefly between arrivals against a client seeded with tiny thresholds.
    import time

    client = fast_pressure_client
    _submit(client, n=1)
    for _ in range(12):
        time.sleep(0.02)
        _submit(client, n=1)

    status = client.get(f"/v1/approvers/{client.alice_id}/status").json()
    assert status["latency_p50_ms"] is not None
    assert status["pressure_state"] in {"elevated", "critical"}
    # queue_depth <= 13 rather than == 13: once pressure reaches critical,
    # the (synchronously-run-in-tests) background governance pass is
    # expected to start auto-approving these low-value, under-threshold
    # requests off the queue -- see test_critical_pressure_triggers_agent
    # for a direct assertion on that behavior.
    assert status["queue_depth"] <= 13


def test_critical_pressure_triggers_offline_auto_approval(fast_pressure_client):
    # Closes the loop end to end: sustained critical pressure should not
    # just be a dashboard number -- it should visibly start resolving the
    # backlog, which is the actual point of the whole project.
    import time

    client = fast_pressure_client
    for _ in range(15):
        time.sleep(0.02)
        _submit(client, n=1)

    ledger = client.get(f"/v1/decisions/recent?limit=200&approver_id={client.alice_id}").json()
    outcomes = {item["outcome"] for item in ledger["items"]}
    assert "auto_approved" in outcomes
