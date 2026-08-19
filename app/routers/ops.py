from __future__ import annotations

from fastapi import APIRouter, Request, Response
from sqlalchemy import text, select, func

from ..db import ApproverModel, DecisionModel
from .deps import get_db

router = APIRouter(tags=["operations"])


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request):
    session = request.app.state.session_factory()
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return Response(content='{"status":"not_ready"}', status_code=503, media_type="application/json")
    finally:
        session.close()


@router.get("/metrics")
async def metrics(request: Request):
    session = request.app.state.session_factory()
    try:
        lines = ["# HELP weir_approver_pressure Current approver pressure.", "# TYPE weir_approver_pressure gauge"]
        for approver in session.scalars(select(ApproverModel)):
            state = await request.app.state.state_store.get_pressure_state(approver.id)
            value = {"normal": 0, "elevated": 1, "critical": 2}.get(state[0] if state else "normal", 0)
            lines.append(f'weir_approver_pressure{{approver_id="{approver.id}"}} {value}')
            depth = await request.app.state.state_store.queue_depth(approver.id)
            lines.append(f'weir_queue_depth{{approver_id="{approver.id}"}} {depth}')
        lines += ["# TYPE weir_decisions_total counter"]
        counts = session.execute(select(DecisionModel.outcome, func.count(DecisionModel.id)).group_by(DecisionModel.outcome))
        for outcome, count in counts:
            lines.append(f'weir_decisions_total{{outcome="{outcome}"}} {count}')
        return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
    finally:
        session.close()

