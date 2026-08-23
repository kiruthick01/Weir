from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


# Statuses that mean "no longer needs action." Anything not in this set
# (queued, hold) is still live and eligible for further governance or
# timeout. Kept here as the single source of truth so the queue-lifecycle
# code (routers + orchestrator) can't drift into checking different strings.
TERMINAL_STATUSES = frozenset({"manually_approved", "auto_approved", "delegated", "timed_out"})


class RequestClassModel(Base):
    __tablename__ = "request_classes"
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    max_wait_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    auto_approve_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_tier: Mapped[str] = mapped_column(String(20), default="medium")


class ApproverModel(Base):
    __tablename__ = "approvers"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    backup_approver_id: Mapped[str | None] = mapped_column(ForeignKey("approvers.id"), nullable=True)


class ApprovalRequestModel(Base):
    __tablename__ = "approval_requests"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid4()))
    source_system: Mapped[str] = mapped_column(String(100))
    external_ref: Mapped[str] = mapped_column(String(255))
    request_class_name: Mapped[str] = mapped_column(ForeignKey("request_classes.name"))
    approver_id: Mapped[str] = mapped_column(ForeignKey("approvers.id"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="queued")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DecisionModel(Base):
    __tablename__ = "decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(ForeignKey("approval_requests.id"), index=True)
    approver_id: Mapped[str] = mapped_column(ForeignKey("approvers.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(50), index=True)
    reason: Mapped[str] = mapped_column(String(2000))
    agent_reasoning: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


def _database_path(database_url: str) -> Path | None:
    if database_url.startswith("sqlite:///./"):
        return Path(database_url.removeprefix("sqlite:///./")).parent
    return None


def create_session_factory(database_url: str):
    if (path := _database_path(database_url)) is not None:
        path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False), engine


def add_decision(session: Session, request_id: str, approver_id: str, outcome: str, reason: str, agent_reasoning: str | None = None) -> DecisionModel:
    decision = DecisionModel(request_id=request_id, approver_id=approver_id, outcome=outcome, reason=reason, agent_reasoning=agent_reasoning)
    session.add(decision)
    session.commit()
    return decision


def recent_decisions(session: Session, limit: int = 50, approver_id: str | None = None) -> list[DecisionModel]:
    statement = select(DecisionModel).order_by(DecisionModel.created_at.desc()).limit(limit)
    if approver_id:
        statement = statement.where(DecisionModel.approver_id == approver_id)
    return list(session.scalars(statement))

