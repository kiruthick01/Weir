"""Integration coverage for the request lifecycle end to end.

These exercise the full FastAPI app (not just the isolated policy engine)
because the bugs this file guards against were all in the *wiring* between
routers, the orchestrator, and the state store: a terminal decision that
never left the live queue, and a delegation that never actually moved the
request to its new approver.
"""

from __future__ import annotations

import os

os.environ.setdefault("WEIR_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WEIR_AGENT_MODE", "offline")

import pytest
from fastapi.testclient import TestClient

from app.db import ApproverModel, RequestClassModel
from main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "lifecycle.db"
    monkeypatch.setenv("WEIR_DATABASE_URL", f"sqlite:///{db_path}")
    with TestClient(app) as test_client:
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
        yield test_client


def _submit(client, n=1, approver_email="alice@example.com"):
    ids = []
    for i in range(n):
        response = client.post(
            "/v1/requests",
            json={
                "source_system": "test",
                "external_ref": f"ref-{approver_email}-{i}-{id(object())}",
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


def test_backlog_ages_and_lifts_pressure_off_normal(client):
    # No requests are ever decided here (mirrors the ramp demo), so the only
    # way pressure can move off "normal" is via the backlog-age signal.
    _submit(client, n=1)
    for _ in range(40):
        _submit(client, n=1)
    status = client.get(f"/v1/approvers/{client.alice_id}/status").json()
    assert status["latency_p50_ms"] is not None
    assert status["pressure_state"] in {"elevated", "critical"}
