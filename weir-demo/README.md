# Weir Demo

Weir is a client-side interactive demonstration of an admission-control layer for human approval workflows. It treats each approver as a finite-capacity resource and makes the full governance pipeline visible:

```text
Pressure → Queue → Agent Proposal → Policy Validation → Decision Ledger
```

The demo shows how Weir detects rising decision latency, builds bounded queues, and applies explainable interventions when an approver reaches sustained Critical pressure.

## Run locally

Requirements: Node.js and npm.

```bash
npm install
npm run dev
```

Open the local Vite URL shown in the terminal. The app runs entirely in the browser and requires no backend, API key, database, or runtime network request after dependencies are installed.

## Demo flow

1. Select an approver card.
2. Click **Ramp Load** to enqueue mixed request classes and values.
3. Watch the target approver move from Normal to Elevated to Critical as synthetic latency samples increase.
4. Observe the bounded queue countdowns and the Governance Agent panel appear at Critical pressure.
5. Review agent proposals, deterministic validation results, fallbacks, and rejected proposals in the ledger.
6. Use **Trigger Agent Cycle** to control the agent manually, or **Reset Demo** to restore the seeded state.

The load ramp deliberately mixes values below and above the low-risk auto-approval threshold so both auto-approval and escalation/delegation paths can be demonstrated. Requests are not resolved during the ramp; the queue visibly builds for presentation purposes.

## Architecture

- **Vite + React + TypeScript** — client application and strict typed state.
- **Tailwind CSS + shadcn/ui** — dark, presentation-friendly dashboard interface.
- **`src/lib/engine.ts`** — pressure math, hysteresis, latency windows, queues, and deadlines.
- **`src/lib/agent.ts`** — deterministic simulation of the Governance Agent, policy validation, and one-retry fallback loop.
- **`src/state/weirReducer.ts`** — reducer actions for enqueueing, ticks, latency samples, agent cycles, and reset.
- **`src/state/WeirProvider.tsx`** — shared state and 250ms simulation tick loop, including automatic agent cycles.
- **`src/components/`** — approver cards, bounded queue, agent proposals, decision ledger, summary strip, legend, and demo controls.

The governance agent is intentionally simulated. It does not call an LLM or external service; it stands in for the real Claude tool-use implementation used in the runnable-codebase track.

## Validation

```bash
npm run build
```

The demo is the client-side simulated companion to the real backend build described in the [runnable-codebase documentation](../documentation/Weir-Agent-Architecture-Update.md).
