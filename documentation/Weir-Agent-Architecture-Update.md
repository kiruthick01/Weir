# Weir — Agent Architecture Update

*Addendum to Weir-Project-Documentation.md — addresses the hackathon's "AI / Agentic Design" judging criterion by introducing the Weir Governance Agent as the reasoning layer above the existing deterministic policy engine.*

---

## Why this update exists

The original architecture is a deterministic capacity-governance state machine: strong systems thinking, but no AI/agentic component — a judge would reasonably ask "where is the agent?" This update adds one, without discarding the thing that made Weir credible in the first place: **explainable, bounded, auditable decisions.**

The fix is not "put an LLM in the approval path." It's: **the agent reasons and proposes; the existing deterministic policy engine still enforces every hard limit.** Agent proposes, policy disposes.

---

## Updated architecture

```
                 ┌─────────────────────────────┐
                 │   Weir Governance Agent      │
                 │   (invoked on state          │
                 │    transitions, batched)     │
                 │                              │
                 │   Observe → Reason → Propose │
                 └───────────────┬──────────────┘
                                 │ read tools        │ propose tools
                                 ▼                    ▼
                 ┌───────────────────────┐  ┌────────────────────────┐
                 │  Pressure / Queue      │  │  Proposal Queue         │
                 │  State (Redis)         │  │  (delegate / approve /  │
                 │                        │  │   escalate / hold)      │
                 └───────────────────────┘  └───────────┬─────────────┘
                                                          │
                                                          ▼
                                          ┌───────────────────────────┐
                                          │  Policy Engine (existing,  │
                                          │  deterministic — validates │
                                          │  every proposal against    │
                                          │  risk tier, value          │
                                          │  threshold, rate limits)   │
                                          └───────────┬───────────────┘
                                        validated │        │ rejected
                                                  ▼        ▼
                                          Committed      Logged as
                                          Decision       rejected
                                          (Ledger)       (Ledger)
```

The agent never writes to the decision ledger directly and never mutates approval state. It only emits proposals; the policy engine is still the sole authority that commits a decision. This keeps the original auditability guarantee (F7) intact even with an LLM in the loop.

---

## When the agent runs

- Triggered on pressure-state transitions (Normal→Elevated, Elevated→Critical) — not per incoming request.
- Re-invoked every 30–60s while sustained in Elevated/Critical, since queue composition keeps changing.
- One invocation per trigger event, given the **full queue and pressure context** for that approver — batch reasoning across all queued requests, not one LLM call per request. This is what makes it reasoning about a system rather than a per-item classifier with extra steps.

## Tools

**Read (context-gathering):**
`get_approver_pressure`, `get_queue_state`, `get_backup_approvers` (with their own current pressure), `get_policy`, `get_recent_decisions`

**Propose (never acts directly):**
`propose_delegate(request_id, target_approver_id, reason)`
`propose_auto_approve(request_id, reason)`
`propose_escalate_to_human(request_id, reason)`
`propose_hold(request_id, reason)` — explicit "no action needed"

## Guardrails

Every proposal passes through the existing policy engine (`validate(proposal)`), which checks risk tier, value threshold, delegation-chain legality, and a **rate limit on auto-approvals per approver per hour** — without this, sustained Critical state could let the agent wave through everything under threshold in one pass. Rejected proposals are logged as rejected, not discarded — "agent proposed X, policy engine said no" is a first-class audit event and the strongest available answer to "why should I trust this."

## Loop shape

Bounded, not open-ended: observe → reason → emit proposals → validate → one retry pass for rejected proposals only (e.g., auto-approve rejected on risk tier → agent falls back to escalate-to-human) → finalize. Capped at 2–3 reasoning passes for predictable latency in a live demo.

Each invocation is stateless — fresh context built entirely from tool calls, no carried memory between runs. This means any past decision can be replayed exactly from the ledger alone.

## Failure mode

Agent error or timeout → fail open, consistent with the existing Redis/Postgres fail-open behavior (NFR: Availability): no auto-decisions are made, requests stay queued, and the outage is logged as "governance agent unavailable."

---

## What this changes in the existing docs

- **F5/F6** (auto-delegate, auto-approve on sustained Critical) are now agent-proposed, policy-validated, rather than directly rule-triggered.
- **F7** (decision ledger) gains a new outcome type: `rejected_proposal`, plus an `agent_reasoning` field on committed decisions.
- **Section 3 tech stack** gains one line: *Agent runtime — Claude (or equivalent LLM) with the tool set above; no change to Redis/Postgres/FastAPI.*
- **Roadmap Stage 2 (MVP)** should list the agent loop as a must-have alongside delegation and auto-approval, not as a stretch goal — it's the primary answer to the AI/Agentic Design judging criterion.
