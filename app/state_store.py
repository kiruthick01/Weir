"""In-process live state for Weir.

The interface is intentionally shaped so this implementation can later be
swapped for a Redis-backed store without changing its callers.  A Redis
implementation can provide the same method names and signatures when Weir
needs coordination across multiple replicas.
"""

from __future__ import annotations

import asyncio
import heapq
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Deque


DEFAULT_LATENCY_WINDOW_SECONDS = 15 * 60
DEFAULT_LATENCY_SAMPLE_COUNT = 50
DEFAULT_POLICY_STATE_COOLDOWN_SECONDS = 60
PRESSURE_STATES = frozenset({"normal", "elevated", "critical"})


@dataclass(frozen=True, slots=True)
class _LatencySample:
    recorded_at: datetime
    latency_ms: int


@dataclass(frozen=True, slots=True)
class _PressureState:
    state: str
    last_transition_at: datetime


class StateStore:
    """Async, in-process equivalent of Weir's three live-state structures."""

    def __init__(
        self,
        *,
        latency_window_seconds: float | None = None,
        max_latency_samples: int = DEFAULT_LATENCY_SAMPLE_COUNT,
        policy_state_cooldown_seconds: float | None = None,
    ) -> None:
        if max_latency_samples < 1:
            raise ValueError("max_latency_samples must be at least 1")

        self.latency_window_seconds = (
            latency_window_seconds
            if latency_window_seconds is not None
            else float(
                os.getenv(
                    "WEIR_LATENCY_WINDOW_SECONDS",
                    DEFAULT_LATENCY_WINDOW_SECONDS,
                )
            )
        )
        self.max_latency_samples = max_latency_samples
        self.policy_state_cooldown_seconds = (
            policy_state_cooldown_seconds
            if policy_state_cooldown_seconds is not None
            else float(
                os.getenv(
                    "POLICY_STATE_COOLDOWN_SECONDS",
                    DEFAULT_POLICY_STATE_COOLDOWN_SECONDS,
                )
            )
        )

        # These dictionaries correspond to:
        # approver:{id}:latency_window
        # approver:{id}:pressure_state
        # queue:{approver_id}
        self._latency_windows: dict[str, Deque[_LatencySample]] = defaultdict(
            lambda: deque(maxlen=self.max_latency_samples)
        )
        self._pressure_states: dict[str, _PressureState] = {}
        self._queues: dict[str, list[tuple[datetime, int, str]]] = defaultdict(list)
        self._queued_deadlines: dict[str, dict[str, datetime]] = defaultdict(dict)
        self._queue_sequence = 0
        self._lock = asyncio.Lock()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        """Normalize naive datetimes as UTC and preserve aware instants."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _discard_old_latency_samples(self, approver_id: str, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.latency_window_seconds)
        samples = self._latency_windows[approver_id]
        while samples and samples[0].recorded_at < cutoff:
            samples.popleft()

    @staticmethod
    def _percentile(values: list[int], percentile: float) -> int | None:
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        # Inclusive linear interpolation, rounded to the integer API type.
        ordered = sorted(values)
        position = (len(ordered) - 1) * percentile
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        result = ordered[lower] + (ordered[upper] - ordered[lower]) * (
            position - lower
        )
        return round(result)

    async def record_decision_latency(self, approver_id: str, latency_ms: int) -> None:
        """Record one decision latency and retain only the active rolling window."""
        if latency_ms < 0:
            raise ValueError("latency_ms must be non-negative")
        now = self._utc_now()
        async with self._lock:
            self._discard_old_latency_samples(approver_id, now)
            self._latency_windows[approver_id].append(
                _LatencySample(recorded_at=now, latency_ms=int(latency_ms))
            )

    async def _get_latency_percentile(
        self, approver_id: str, percentile: float
    ) -> int | None:
        now = self._utc_now()
        async with self._lock:
            self._discard_old_latency_samples(approver_id, now)
            values = [sample.latency_ms for sample in self._latency_windows[approver_id]]
            return self._percentile(values, percentile)

    async def get_latency_p50(self, approver_id: str) -> int | None:
        return await self._get_latency_percentile(approver_id, 0.50)

    async def get_latency_p90(self, approver_id: str) -> int | None:
        return await self._get_latency_percentile(approver_id, 0.90)

    async def get_pressure_state(
        self, approver_id: str
    ) -> tuple[str, datetime] | None:
        async with self._lock:
            current = self._pressure_states.get(approver_id)
            if current is None:
                return None
            return current.state, current.last_transition_at

    async def set_pressure_state(
        self, approver_id: str, state: str, now: datetime
    ) -> bool:
        """Set pressure state if valid and outside the transition cooldown.

        Returns ``True`` only when the stored state actually changed (including
        the first state written for an approver).
        """
        state = state.lower()
        if state not in PRESSURE_STATES:
            raise ValueError(f"invalid pressure state: {state!r}")
        now = self._as_utc(now)
        async with self._lock:
            current = self._pressure_states.get(approver_id)
            if current is not None:
                if current.state == state:
                    return False
                elapsed = (now - current.last_transition_at).total_seconds()
                if elapsed < self.policy_state_cooldown_seconds:
                    return False
            self._pressure_states[approver_id] = _PressureState(state, now)
            return True

    async def enqueue(
        self, approver_id: str, request_id: str, deadline: datetime
    ) -> None:
        """Add or update a request in the approver's deadline-ordered queue."""
        deadline = self._as_utc(deadline)
        async with self._lock:
            self._queue_sequence += 1
            self._queued_deadlines[approver_id][request_id] = deadline
            heapq.heappush(
                self._queues[approver_id],
                (deadline, self._queue_sequence, request_id),
            )

    async def dequeue(self, approver_id: str, request_id: str) -> None:
        async with self._lock:
            self._queued_deadlines[approver_id].pop(request_id, None)

    async def queue_depth(self, approver_id: str) -> int:
        async with self._lock:
            return len(self._queued_deadlines[approver_id])

    async def queue_snapshot(self, approver_id: str) -> list[dict[str, object]]:
        async with self._lock:
            entries = sorted(
                self._queued_deadlines[approver_id].items(),
                key=lambda item: (item[1], item[0]),
            )
            return [
                {"request_id": request_id, "deadline": deadline}
                for request_id, deadline in entries
            ]

    async def timed_out_requests(
        self, approver_id: str, now: datetime
    ) -> list[str]:
        now = self._as_utc(now)
        async with self._lock:
            return [
                request_id
                for request_id, deadline in sorted(
                    self._queued_deadlines[approver_id].items(),
                    key=lambda item: (item[1], item[0]),
                )
                if deadline < now
            ]


# Shared by all routers in the local single-process deployment.
state_store = StateStore()
