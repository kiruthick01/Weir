from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import RequestClassModel
from .deps import get_db

router = APIRouter(prefix="/v1/config", tags=["config"])


class PolicyUpdate(BaseModel):
    request_class: str
    max_wait_seconds: int | None = None
    auto_approve_threshold: float | None = None
    risk_tier: Literal["low", "medium", "high"] | None = None

    @field_validator("max_wait_seconds")
    @classmethod
    def _positive_wait(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("max_wait_seconds must be positive")
        return value

    @field_validator("auto_approve_threshold")
    @classmethod
    def _non_negative_threshold(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("auto_approve_threshold must be non-negative")
        return value


@router.get("/policy")
def get_policy(db: Session = Depends(get_db)):
    return {"request_classes": [{"name": item.name, "max_wait_seconds": item.max_wait_seconds, "auto_approve_threshold": item.auto_approve_threshold, "risk_tier": item.risk_tier} for item in db.scalars(select(RequestClassModel).order_by(RequestClassModel.name))]}


@router.put("/policy")
def update_policy(body: PolicyUpdate, request: Request, x_admin_key: str | None = Header(None), db: Session = Depends(get_db)):
    if not x_admin_key or x_admin_key != request.app.state.settings.admin_api_key:
        raise HTTPException(401, "invalid admin key")
    item = db.get(RequestClassModel, body.request_class)
    if not item:
        raise HTTPException(404, "request class not found")
    if body.max_wait_seconds is not None:
        item.max_wait_seconds = body.max_wait_seconds
    if body.auto_approve_threshold is not None:
        item.auto_approve_threshold = body.auto_approve_threshold
    if body.risk_tier is not None:
        item.risk_tier = body.risk_tier
    db.commit()
    return {"name": item.name, "max_wait_seconds": item.max_wait_seconds, "auto_approve_threshold": item.auto_approve_threshold, "risk_tier": item.risk_tier}

