# Weir Demo

Weir is a client-side interactive demonstration of an admission-control layer for human approval workflows. It treats approvers as finite-capacity resources, visualizes pressure moving from Normal to Elevated to Critical, builds bounded queues, invokes a simulated governance agent, validates proposals deterministically, and exposes every outcome in an append-only decision ledger.

Run it locally with:

```bash
npm install && npm run dev
```

The app is fully client-side and requires no backend, API key, or runtime network call; it is the simulated companion to the real backend build in the [runnable-codebase track](../documentation/Weir-Agent-Architecture-Update.md).
