# Weir — Admission Control for Human Approvers

*An enterprise capacity-governance layer that treats approval bottlenecks as a queueing problem, not a UX problem.*

**Audience:** engineering team (build reference), hackathon judges/stakeholders (architecture credibility), future contributors (onboarding).

---

## 1. Project Overview & Vision

### The problem

Every enterprise approval workflow tool — procurement sign-off, expense approval, access requests, contract review — treats slow approvals as an inbox-design problem. Better notifications, smarter routing rules, a nicer dashboard. None of that addresses the actual failure mode.

An approver is a **finite-capacity resource with a measurable decision-latency curve** — functionally identical to a GPU with finite KV-cache capacity serving inference requests. When an approver is oversubscribed, requests don't fail loudly. They silently accumulate in an inbox, latency creeps up for everyone waiting behind them, and the organization has no signal that this is happening until someone escalates in frustration. Nobody measures the bottleneck; they just blame "the process."

Workflow automation tools are built by automation engineers optimizing for routing logic and UI polish. Nobody has applied **systems-governance thinking** — the discipline used to manage overloaded infrastructure — to the equivalent problem in human approval chains.

### The vision

Weir is an admission-control layer that sits in front of any approval-driven workflow (procurement, access requests, expense sign-off, contract review) and actively governs load the way a capacity-aware proxy governs traffic to a constrained backend:

- Treats each approver's live decision latency as a **pressure signal**, not an afterthought.
- Applies **named pressure states** (Normal / Elevated / Critical) with hysteresis, so a single slow day doesn't trigger overreaction.
- **Queues with a bounded max-wait** instead of letting requests pile into an inbox indefinitely.
- **Auto-delegates or auto-approves** low-risk requests under sustained overload, with every decision logged and explainable — never a silent, unaccountable action.

### Core goals

1. Make approver overload **visible and measurable** in real time, not discovered after an SLA is already blown.
2. Replace unbounded inbox pile-up with a **governed queue** that has explicit, tunable wait guarantees per request class.
3. Provide **graceful degradation** (delegation, auto-approval under threshold) instead of binary "wait forever or escalate manually."
4. Make every automated intervention **fully auditable** — who/what made the call, on what signal, and why.

### Unique value proposition

Weir isn't another workflow builder. It's infrastructure-grade **admission control**, ported directly from distributed-systems capacity governance, applied to the approval layer of the enterprise stack that every other tool treats as a UI problem. The differentiator is the model, not the interface.

---

## 2. Key Features & Requirements

### Core functional requirements

| ID | Requirement |
|---|---|
| F1 | Ingest approval requests from one or more source systems (ticketing, procurement, HR) via webhook or polling connector. |
| F2 | Maintain a live decision-latency signal per approver, computed from a rolling window of recent decision times. |
| F3 | Classify each approver's current state as Normal / Elevated / Critical using consecutive-sample thresholds and hysteresis (no flapping on noisy data). |
| F4 | Queue incoming requests per approver with a configurable, per-request-class max-wait SLA. |
| F5 | On sustained Critical state, auto-delegate queued requests to a configured backup approver. |
| F6 | On sustained Critical state, auto-approve requests below a configured risk/value threshold, subject to policy config. |
| F7 | Record every decision (queued, delegated, auto-approved, released, timed out) to a durable, queryable decision ledger with a human-readable reason. |
| F8 | Expose a live dashboard: current pressure per approver, queue depth, recent decisions, and manual override controls. |
| F9 | Allow administrators to configure per-approver thresholds, per-request-class SLAs, and delegation chains via policy config (not code changes). |

### User stories

- *As an approver*, I want my queue to only ever show requests I can reasonably act on soon, so I'm not staring at an unbounded backlog.
- *As a requester*, I want to know my request will either be actioned within a bounded time or explicitly escalated — not silently stuck.
- *As a compliance officer*, I want a full audit trail of every auto-approved or auto-delegated decision, with the reasoning attached, so I can defend it in a review.
- *As an operations lead*, I want a live view of which approvers are overloaded right now, so I can rebalance before it becomes a business problem.
- *As an administrator*, I want to tune thresholds and delegation rules without needing an engineer to redeploy anything.

### Non-functional requirements

- **Performance:** Policy evaluation (pressure state + action selection) must add negligible latency to the request path — target under 10ms median overhead per decision, consistent with the source pattern this design is ported from.
- **Availability:** The system must fail open on dependency failure (e.g., signal store unreachable) rather than blocking all approvals — availability of the underlying workflow takes priority over strict governance during an outage, and this tradeoff must be explicitly logged when it happens.
- **Scalability:** Must support governing hundreds of concurrent approvers and thousands of in-flight requests without per-approver state becoming a bottleneck; state should be externalized (not held only in a single process) so the service can run multiple replicas.
- **Auditability:** Every automated action must be reconstructable after the fact — who/what decided, which signal triggered it, and what the alternative would have been.
- **Security:** Auto-approval thresholds and delegation rules must be access-controlled; only authorized administrators can modify policy config. Audit log must be append-only / tamper-evident.

---

## 3. System Architecture & Tech Stack

### Recommended stack

| Layer | Choice | Rationale |
|---|---|---|
| API / policy service | **Python (FastAPI)** | Fast to iterate in a hackathon window; async-native, matches the request/response shape of the governance pattern. |
| Policy engine | Plain Python state machine (no external rules engine) | Keeps the core governance logic transparent and testable — the whole point is explainability, not a black-box rules DSL. |
| Signal store / distributed state | **Redis** | Rolling latency windows, per-approver pressure state, and queue coordination all fit Redis's data structures (sorted sets, hashes) well, and it supports multi-replica coordination if scaled beyond a single instance. |
| Decision ledger | **PostgreSQL** | Durable, queryable audit trail; relational fits the "requests joined to approvers joined to decisions" shape naturally. |
| Frontend dashboard | **Next.js + TypeScript** | Fast to build a live-updating operator view; matches common hackathon judging expectations for a polished demo. |
| Connectors | Lightweight webhook receivers + a generic polling adapter | Avoids hard-coupling to one specific source system (Freshworks, Jira, ServiceNow, etc.) during the hackathon; a single normalized "ApprovalRequest" schema decouples the core engine from any one integration. |
| Hosting (demo) | **Docker Compose locally**, deployable to any container host (Render, Railway, or a single VM) for the live demo | Keeps setup fast and judge-reproducible; no need for a full Kubernetes story to prove the concept. |

### High-level architecture

```mermaid
flowchart TB
    subgraph Sources["Request Sources"]
        A1[Procurement System]
        A2[Access Request Tool]
        A3[Expense System]
    end

    A1 -->|webhook| INGEST
    A2 -->|webhook| INGEST
    A3 -->|poll adapter| INGEST

    INGEST[Ingest / Normalization Layer] --> PIPE

    subgraph Weir["Weir Core"]
        PIPE[Policy Pipeline]
        PIPE --> PE[Pressure Evaluation]
        PE --> AS[Action Selection]
        AS --> Q[Bounded Queue Manager]
        AS --> DEL[Delegation Engine]
        AS --> AA[Auto-Approval Engine]
    end

    PE <-->|latency signal, pressure state| REDIS[(Redis: Signal + Queue State)]
    Q <-->|queue membership, deadlines| REDIS

    Q --> APPROVER[Approver Inbox / Notification]
    DEL --> APPROVER
    AA --> OUT[Decision Output]
    APPROVER --> OUT

    OUT --> LEDGER[(PostgreSQL: Decision Ledger)]
    LEDGER --> DASH[Operator Dashboard]
    REDIS --> DASH
```

### Policy pipeline (mirrors proven capacity-governance design)

```mermaid
flowchart LR
    S[Signals: decision latency, queue depth, SLA breach rate] --> PE[Pressure Evaluation]
    PE -->|Normal / Elevated / Critical, with hysteresis| AP[Approver Policy]
    AP --> AS[Action Selection]
    AS -->|Pass| PASS[Route to approver normally]
    AS -->|Queue| QUEUE[Bounded wait, tracked deadline]
    AS -->|Delegate| DELEGATE[Route to backup approver]
    AS -->|Auto-approve| AUTO[Approve under threshold, logged]
```

Each stage is a discrete, independently testable unit — this is a deliberate architectural choice, not an afterthought: it's what allows thresholds, delegation rules, and auto-approval policy to be tuned per approver or per request class without rewriting the pipeline itself.

---

## 4. Data Models & Database Schema

### Core entities

- **Approver** — a person (or role) capable of actioning requests.
- **ApprovalRequest** — a normalized request awaiting a decision, regardless of source system.
- **Decision** — a durable record of what happened to a request (queued, delegated, auto-approved, manually approved, timed out).
- **PolicyConfig** — per-approver or per-request-class thresholds and rules.
- **PressureSample** — a point-in-time observation of an approver's load (kept in Redis for live state; periodically flushed to Postgres for historical analysis).

### Schema (PostgreSQL)

```sql
CREATE TABLE approvers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    role            TEXT NOT NULL,
    backup_approver_id UUID REFERENCES approvers(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE request_classes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL UNIQUE,       -- e.g. 'procurement_low_value'
    max_wait_seconds    INTEGER NOT NULL,
    auto_approve_threshold NUMERIC,                 -- null = auto-approval disabled for this class
    risk_tier           TEXT NOT NULL                -- 'low' | 'medium' | 'high'
);

CREATE TABLE approval_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system   TEXT NOT NULL,
    external_ref    TEXT NOT NULL,                  -- ID in the source system
    request_class_id UUID NOT NULL REFERENCES request_classes(id),
    approver_id     UUID NOT NULL REFERENCES approvers(id),
    payload         JSONB NOT NULL,                 -- normalized request details
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_system, external_ref)
);

CREATE TABLE decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id      UUID NOT NULL REFERENCES approval_requests(id),
    outcome         TEXT NOT NULL,                  -- 'queued' | 'delegated' | 'auto_approved' | 'manually_approved' | 'timed_out' | 'rejected'
    reason          TEXT NOT NULL,                  -- human-readable, e.g. 'sustained_critical_pressure_auto_approved'
    pressure_state  TEXT,                            -- state at time of decision
    signal_snapshot JSONB,                            -- raw signal values at decision time
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE pressure_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    approver_id     UUID NOT NULL REFERENCES approvers(id),
    latency_p50_ms  INTEGER,
    queue_depth     INTEGER,
    pressure_state  TEXT NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Relationships

- One `approver` → many `approval_requests` (as the assigned approver).
- One `approver` → optional one `backup_approver` (self-referential, for delegation).
- One `request_class` → many `approval_requests` (defines its SLA and auto-approval policy).
- One `approval_request` → many `decisions` (a request's lifecycle can have multiple recorded events — queued, then later delegated, then finally decided).

### Live state (Redis — not durable, mirrors into Postgres periodically)

- `approver:{id}:latency_window` — sorted set of recent decision timestamps, used to compute rolling latency.
- `approver:{id}:pressure_state` — current state string + last-transition timestamp, for hysteresis/cooldown enforcement.
- `queue:{approver_id}` — sorted set of queued request IDs, scored by enqueue deadline.

---

## 5. API & Integration Specs

### Core endpoints

**`POST /v1/requests`** — ingest a new approval request (from a connector or direct integration).

Request:
```json
{
  "source_system": "procurement-tool",
  "external_ref": "PO-48213",
  "request_class": "procurement_low_value",
  "approver_email": "jane.doe@company.com",
  "payload": {
    "amount": 4200,
    "vendor": "Acme Supplies",
    "requested_by": "alex@company.com"
  }
}
```

Response:
```json
{
  "request_id": "b3f1...",
  "status": "queued",
  "pressure_state": "elevated",
  "estimated_wait_seconds": 120
}
```

**`GET /v1/approvers/{id}/status`** — current pressure state and queue depth for one approver.

```json
{
  "approver_id": "a1c9...",
  "pressure_state": "critical",
  "latency_p50_ms": 84000,
  "queue_depth": 14,
  "state_since": "2026-08-18T09:12:00Z"
}
```

**`GET /v1/decisions/recent`** — recent decision ledger entries (dashboard-facing, paginated).

**`POST /v1/decisions/{request_id}/override`** — manual admin override (e.g., force-approve, force-reassign), requires admin auth.

**`GET /v1/config/policy`** / **`PUT /v1/config/policy`** — read/update per-request-class SLA and auto-approval thresholds.

### Operational endpoints

- `GET /healthz`, `GET /readyz` — standard health checks.
- `GET /metrics` — Prometheus-format metrics (pressure gauge per approver, decision counters by outcome, queue depth).

### External integrations (connectors)

Each connector implements a thin adapter that normalizes source-system events into the `POST /v1/requests` shape:

- **Webhook-based** (preferred where available): source system pushes an event on request creation; adapter validates payload shape and forwards.
- **Polling-based** (fallback): adapter polls a source system's API on an interval, diffing against previously seen request IDs.

For the hackathon demo, a single mock connector simulating a procurement/access-request system is sufficient — the adapter interface itself is the reusable, integration-agnostic piece.

---

## 6. Step-by-Step Installation & Setup

```bash
# 1. Clone the repository
git clone https://github.com/<your-org>/weir.git
cd weir

# 2. Copy environment template and configure
cp .env.example .env
# Edit .env — set DATABASE_URL, REDIS_URL, and any connector credentials

# 3. Start dependencies (Postgres + Redis) via Docker Compose
docker compose up -d postgres redis

# 4. Install backend dependencies (Python / FastAPI)
cd service
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 5. Run database migrations
alembic upgrade head

# 6. Seed example approvers, request classes, and policy config
python scripts/seed.py

# 7. Start the policy service
uvicorn app.main:app --reload --port 8080

# 8. In a separate terminal, install and run the dashboard
cd ../dashboard
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8080
npm run dev

# 9. Open the dashboard
# http://localhost:3000

# 10. (Optional) Run the mock connector to simulate incoming requests
cd ../connectors/mock
python simulate_requests.py --rate 5 --duration 300
```

### Environment variables (`.env`)

```
DATABASE_URL=postgresql://weir:weir@localhost:5432/weir
REDIS_URL=redis://localhost:6379/0
POLICY_STATE_CONSECUTIVE_SAMPLES=2
POLICY_STATE_COOLDOWN_SECONDS=30
POLICY_STATE_HYSTERESIS_PCT=10
DEFAULT_QUEUE_MAX_WAIT_SECONDS=600
ADMIN_API_KEY=change-me-before-demo
```

### Quick smoke test

```bash
curl -X POST http://localhost:8080/v1/requests \
  -H "Content-Type: application/json" \
  -d '{"source_system":"mock","external_ref":"TEST-1","request_class":"procurement_low_value","approver_email":"jane.doe@company.com","payload":{"amount":100}}'

curl http://localhost:8080/v1/approvers/<approver_id>/status
```

---

## 7. Project Roadmap

### Stage 1 — Qualification Prototype (pre-hackathon)

- Core policy pipeline: pressure evaluation → action selection, single-signal (decision latency only).
- In-memory or single-Redis-instance queueing with bounded max-wait.
- Minimal dashboard: current pressure per approver, live queue depth.
- One mock connector simulating a request source.
- **Deliverable:** clickable prototype/demo + 1–2 minute walkthrough video for Stage 1 submission.

### MVP — 24-Hour Build (Stage 2, if shortlisted)

- Full policy pipeline with hysteresis and cooldowns (anti-flapping, ported directly from the proven design pattern this project is based on).
- Delegation to backup approver on sustained Critical state.
- Auto-approval under configurable threshold, with full decision-ledger logging.
- Postgres-backed durable decision ledger (not just in-memory).
- Polished operator dashboard: pressure states, queue depth, recent decisions, manual override control.
- Live demo script: simulate load ramping an approver into Critical state, show queueing → delegation → auto-approval kick in live, on stage.

### Phase 2 — Post-Hackathon Hardening

- Real connector(s) to at least one actual source system (e.g., a ticketing or procurement API) rather than only the mock simulator.
- Distributed, multi-replica policy service coordinating through Redis (matching the proven multi-replica admission-control pattern), rather than a single instance.
- Multi-signal pressure model: incorporate queue depth and historical SLA-breach rate alongside raw decision latency.
- Role-based access control for policy configuration and manual overrides.
- Basic auth / API-key protection on all admin and override endpoints.

### Future Enhancements

- Configurable escalation chains beyond a single backup approver (multi-level delegation).
- Per-request-class risk scoring to inform auto-approval eligibility dynamically, rather than a static threshold.
- Historical replay tooling: test a proposed policy/threshold change against real historical request data before deploying it live.
- Integration marketplace: publishable connector adapters for common enterprise systems (ServiceNow, Jira, SAP Ariba, etc.).
- Chaos/failure testing: verify behavior when Redis or Postgres is unavailable, confirming fail-open behavior holds under real conditions rather than only in design intent.
