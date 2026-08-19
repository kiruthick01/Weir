# Weir — Admission Control for Human Approval

Weir is an admission-control layer for human approval workflows. It treats an approver as a finite-capacity resource with a measurable decision-latency curve, then governs incoming approval requests with pressure-aware queuing, bounded wait times, delegation, and constrained automation.

The system is designed to answer not only “what happened?” but also “why was this action allowed?” Every automated action, agent proposal, policy rejection, timeout, and manual override is intended to be reconstructable from the decision ledger.

## Core idea

An approver has finite decision capacity. As recent decision latency and queue pressure increase, Weir moves through three states:

```text
Normal  ->  Elevated  ->  Critical
```

Pressure transitions use consecutive observations, cooldown, and hysteresis so noisy measurements do not cause state flapping. The deterministic policy engine selects admission behavior, while the governance agent is invoked only when sustained pressure needs contextual reasoning.

The governance agent is proposal-only:

```text
request
  -> pressure evaluation
  -> deterministic action selection
  -> queue / pass / timeout eligibility
  -> agent proposal when pressure requires reasoning
  -> deterministic validation
  -> committed decision or rejected_proposal audit event
```

The agent never writes to the ledger and never mutates approval state directly.

## Local hackathon stack

This build is intentionally runnable on one machine without external infrastructure:

- FastAPI provides the HTTP API and serves the dashboard.
- SQLite, through SQLAlchemy, stores request classes, approvers, approval requests, and decisions.
- `app/state_store.py` provides an asyncio-lock-protected in-process replacement for Redis. It stores rolling decision latency, pressure state, and deadline-ordered queues.
- `app/policy_engine.py` contains the readable deterministic state machine for pressure evaluation, action selection, and proposal validation.
- `app/governance_agent.py` provides Anthropic live mode and a deterministic offline mode.
- `dashboard/static/` contains the framework-free dashboard: plain HTML, CSS, and JavaScript polling with `fetch()`.

## Setup

From the repository root:

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Install the declared Python dependencies:

```bash
pip install -e .
```

If using a requirements file in your deployment checkout, the equivalent command is:

```bash
pip install -r requirements.txt
```

Configure environment variables as needed:

```dotenv
WEIR_DATABASE_URL=sqlite:///./data/weir.db
WEIR_AGENT_MODE=offline
WEIR_ADMIN_API_KEY=dev-admin-key
POLICY_STATE_COOLDOWN_SECONDS=60
POLICY_STATE_CONSECUTIVE_SAMPLES=2
POLICY_STATE_HYSTERESIS_PCT=10
```

Live Anthropic mode additionally requires an API key supported by the Anthropic SDK and:

```dotenv
WEIR_AGENT_MODE=live
ANTHROPIC_API_KEY=your-key
```

Seed the local database:

```bash
python scripts/seed.py
```

The seed creates five example approvers, reciprocal backup pairs, and three request classes. It is idempotent and updates existing seed rows by their stable keys.

Start the API from the repository root:

```bash
uvicorn main:app --reload --port 8080
```

Open the dashboard at [http://localhost:8080](http://localhost:8080).

> If the application is packaged under a `service/` directory in a later deployment layout, the equivalent command is `uvicorn app.main:app --reload --port 8080` from that service directory.

## Live demo

In a second terminal, from the repository root:

```bash
python scripts/simulate_requests.py --ramp --rate 3 --duration 180
```

The simulator posts synthetic requests and prints each response's status and pressure state inline. It randomizes request classes and payload amounts, including values both below and above the low-value auto-approval threshold.

To stress one approver specifically:

```bash
python scripts/simulate_requests.py \
  --approver-email alice.approver@example.com \
  --ramp --rate 3 --duration 180
```

Ramp mode deliberately does not simulate approvers completing requests. This is intentional for the stage demo: the queue is allowed to build, latency pressure remains visible, and the selected approver can progress from Normal to Elevated to Critical.

Available simulator options:

```text
--rate REQUESTS_PER_SECOND   default: 1
--duration SECONDS            default: 120
--api-url URL                 default: http://localhost:8080
--approver-email EMAIL        target one seeded approver
--ramp                        increase traffic over the run
```

## Dashboard

The dashboard is served directly from `/` with no frontend build step. It provides:

- Live/degraded health indicator from `/healthz` and `/readyz`.
- One pressure card per approver with name, pressure state, p50 latency, queue depth, and state age.
- Selected-approver queue with deadline countdowns and overdue highlighting.
- Force Approve and Force Reassign controls using the admin key prompted on first use.
- The newest 50 decision-ledger entries.
- Expandable agent reasoning for agent-involved decisions.
- Visually distinct `rejected_proposal` entries so “agent proposed X, policy said no” remains visible as a trust signal.

## API surface

### Requests

`POST /v1/requests`

Creates or idempotently returns an approval request. The body is:

```json
{
  "source_system": "procurement",
  "external_ref": "po-123",
  "request_class": "procurement_low_value",
  "approver_email": "alice.approver@example.com",
  "payload": {"amount": 420, "currency": "USD"}
}
```

The response contains:

```json
{
  "request_id": "...",
  "status": "queued",
  "pressure_state": "normal",
  "estimated_wait_seconds": 300
}
```

### Approvers and queues

```text
GET /v1/approvers
GET /v1/approvers/{id}/status
GET /v1/approvers/{id}/queue
```

Status includes pressure state, p50 decision latency, queue depth, and state-since timestamp. Queue entries include request ID, source system, request class, enqueue time, deadline, and remaining time.

### Decision ledger

```text
GET  /v1/decisions/recent?limit=50&offset=0&approver_id=optional
POST /v1/decisions/{request_id}/override
```

Override requests require:

```text
X-Admin-Key: <WEIR_ADMIN_API_KEY>
```

The override body is either:

```json
{"action": "force_approve", "reason": "business owner confirmed"}
```

or:

```json
{
  "action": "force_reassign",
  "target_approver_id": "backup-id",
  "reason": "primary approver unavailable"
}
```

Manual decisions are recorded with a `manual_override: ` reason prefix.

### Policy configuration

```text
GET /v1/config/policy
PUT /v1/config/policy
```

Policy updates require `X-Admin-Key` and can update `max_wait_seconds`, `auto_approve_threshold`, and `risk_tier` for a request class.

### Operations

```text
GET /healthz
GET /readyz
GET /metrics
```

`/readyz` checks that the SQLite database connection works. `/metrics` emits hand-formatted Prometheus text with pressure gauges, queue-depth gauges, and decision counters.

## Default seeded policy

| Request class | Max wait | Auto-approve threshold | Risk tier |
|---|---:|---:|---|
| `procurement_low_value` | 300 seconds | 1000 | low |
| `procurement_high_value` | 1800 seconds | disabled | high |
| `access_request_standard` | 600 seconds | disabled | medium |

Auto-approval is only eligible for permitted risk tiers, values under the configured threshold, and approvers who have not exceeded the hourly auto-approval limit. Delegation is only legal to the configured backup approver.

## Fail-open behavior

Weir is designed not to turn a state-store or agent outage into an approval outage:

- State and agent failures are logged as degraded-mode events.
- Requests continue through the minimum safe queue path.
- An unavailable governance agent produces no proposals and does not write decisions.
- Proposal validation failures are recorded as first-class `rejected_proposal` entries.
- Each rejected proposal gets at most one constrained fallback attempt.
- Timed-out queue entries receive explicit `timed_out` ledger decisions.

## Repository layout

```text
app/
  db.py                 SQLAlchemy models and SQLite session setup
  governance_agent.py   Offline/live proposal-only governance agent
  orchestrator.py       Agent, policy, state, and ledger coordination
  policy_engine.py      Deterministic pressure/action/validation logic
  settings.py           Environment-backed application settings
  state_store.py        In-process Redis-shaped live-state store
  routers/              FastAPI request, approver, decision, config, and ops APIs
  tests/                Policy engine tests
dashboard/static/       Single-page dashboard assets
scripts/                Database seeding and traffic simulation
main.py                 FastAPI application and router/static wiring
```

## What's simplified vs. the full design

These are intentional hackathon-scope swap points for Phase 2 hardening:

- SQLite → Postgres for production durability, concurrency, migrations, and operational tooling.
- In-process state store → Redis for rolling windows, pressure state, and queues shared across replicas.
- Static dashboard → Next.js for a separately built production frontend with richer navigation and authentication UX.

The policy engine is intentionally not simplified into a rules DSL or opaque service. Its plain Python state machine is a core design requirement and should remain easy for a judge, operator, or auditor to read.

