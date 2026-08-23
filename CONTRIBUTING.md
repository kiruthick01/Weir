# Contributing to Weir

Thanks for helping improve Weir. The project is actively evolving and welcomes
focused fixes, documentation improvements, and new integrations.

- Open an issue before starting a large feature or architectural change.
- Keep pull requests focused and explain the operational trade-offs.
- Run `pytest` before submitting a pull request.
- Update the README or documentation when behavior or setup changes.
- Keep `app/state_store.py` focused on queues, latency, and pressure state.
- Keep `app/policy_engine.py` focused on deterministic admission and proposal validation.
- Do not let the governance agent write directly to the ledger or mutate approval state.
- Include tests for new policy behavior and lifecycle changes.
- Use the existing formatting and naming conventions.
- In security-sensitive reports, avoid publishing exploitable details in a public issue.
