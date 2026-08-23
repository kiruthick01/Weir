• The repo currently has two separate demos for two different purposes:

  1. weir-demo/ — the polished, self-contained product demo

  This is the one to use for a presentation or judging walkthrough.

  It runs entirely in the browser with simulated state:

  cd weir-demo
  npm install
  npm run dev

  Then open the Vite URL, usually:

  http://localhost:5173

  Use this flow:

  1. Select an approver.
  2. Click Ramp Load.
  3. Watch pressure move toward Critical.
  4. Review the Governance Agent proposals.
  5. Inspect validation results and the decision ledger.

  It does not use FastAPI, SQLite, or real API requests.

  2. main.py + dashboard/static/ — the backend-connected operator dashboard

  This is the runnable backend implementation and its basic HTML/CSS/JS frontend.

  Run it from the repository root:

  python scripts/seed.py
  uvicorn main:app --reload --port 8080

  Open:

  http://localhost:8080

  In another terminal, generate backend traffic:

  python scripts/simulate_requests.py --ramp --rate 3 --duration 180

  This version demonstrates:

  - FastAPI routes
  - SQLite persistence
  - real API polling
  - queue state
  - pressure state
  - decision ledger
  - manual approval/reassignment overrides

  The important distinction is:

   Directory            Purpose                              Connected to backend?
  ━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━
   weir-demo/           Polished presentation prototype      No
  ───────────────────  ───────────────────────────────────  ───────────────────────
   dashboard/static/    Basic backend-connected dashboard    Yes
  ───────────────────  ───────────────────────────────────  ───────────────────────
   app/, main.py        Backend/API implementation           N/A

  The duplication exists because the project was built in two tracks: a polished client-side concept demo for quick presentation, and a runnable backend
  implementation with a simpler dashboard proving the actual API behavior. The documentation also refers to a future Next.js frontend, but that does not exist in
  this repository.

  For showing the product right now, use weir-demo. For proving the backend works end-to-end, use the Uvicorn version.