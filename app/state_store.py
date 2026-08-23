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
_PRESSURE_SEVERITY = {"normal": 0, "elevated": 1, "critical": 2}


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
        self._queued_enqueued_at: dict[str, dict[str, datetime]] = defaultdict(dict)
        self._queue_sequence = 0
        self._lock = asyncio.Lock()

        # Pressure-evaluation bookkeeping, owned by the store instance instead
        # of a module-level global so it is lock-protected, cannot leak across
        # unrelated StateStore instances, and cannot be corrupted by CPython
        # reusing a garbage-collected instance's id().
        self._consecutive_observations: dict[str, dict[str, int]] = defaultdict(dict)
        self._last_agent_run: dict[str, datetime] = {}

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

        The cooldown only gates *downgrades* (critical -> elevated -> normal,
        i.e. things look like they're recovering) -- that's the direction
        where flapping actually matters, and where you want to be sure the
        improvement is real before declaring it. An *upgrade* (things are
        getting worse) always applies immediately once the policy engine's
        consecutive-sample/hysteresis conditions are met: an overloaded
        approver should never wait out a cooldown clock to be recognized as
        overloaded. This also means an approver's very first pressure
        evaluation -- which always writes an implicit "normal" baseline --
        can't accidentally arm a minute-long cooldown that delays the first
        *real* transition.

        Returns ``True`` only when the stored state actually changed
        (including the first state written for an approver).
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
                is_upgrade = _PRESSURE_SEVERITY[state] > _PRESSURE_SEVERITY[current.state]
                if not is_upgrade:
                    elapsed = (now - current.last_transition_at).total_seconds()
                    if elapsed < self.policy_state_cooldown_seconds:
                        return False
            self._pressure_states[approver_id] = _PressureState(state, now)
            return True

    async def enqueue(
        self,
        approver_id: str,
        request_id: str,
        deadline: datetime,
        *,
        enqueued_at: datetime | None = None,
    ) -> None:
        """Add or update a request in the approver's deadline-ordered queue.

        ``enqueued_at`` defaults to now and drives ``oldest_queue_age_ms``. A
        transfer (delegation/reassignment) should pass ``enqueued_at=now`` so
        the receiving approver's own pressure signal only reflects backlog
        accrued under their ownership, not staleness inherited from whoever
        held the request before.
        """
        deadline = self._as_utc(deadline)
        now = self._utc_now()
        enqueued_at = self._as_utc(enqueued_at) if enqueued_at is not None else now
        async with self._lock:
            self._queue_sequence += 1
            self._queued_deadlines[approver_id][request_id] = deadline
            self._queued_enqueued_at[approver_id][request_id] = enqueued_at
            heapq.heappush(
                self._queues[approver_id],
                (deadline, self._queue_sequence, request_id),
            )

    async def dequeue(self, approver_id: str, request_id: str) -> None:
        async with self._lock:
            self._queued_deadlines[approver_id].pop(request_id, None)
            self._queued_enqueued_at[approver_id].pop(request_id, None)

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
                {
                    "request_id": request_id,
                    "deadline": deadline,
                    "enqueued_at": self._queued_enqueued_at[approver_id].get(request_id),
                }
                for request_id, deadline in entries
            ]

    async def deadline_for(self, approver_id: str, request_id: str) -> datetime | None:
        async with self._lock:
            return self._queued_deadlines[approver_id].get(request_id)

    async def oldest_queue_age_ms(self, approver_id: str, now: datetime) -> int | None:
        """Age, in milliseconds, of the longest-waiting item still queued.

        This is Weir's live-demo proxy for "decision latency": an approver
        who is genuinely falling behind has requests visibly aging in their
        queue even before any of them are formally decided, so pressure can
        rise from backlog alone instead of only from completed decisions.
        """
        now = self._as_utc(now)
        async with self._lock:
            enqueued_ats = self._queued_enqueued_at[approver_id].values()
            if not enqueued_ats:
                return None
            oldest = min(enqueued_ats)
            return max(0, int((now - oldest).total_seconds() * 1000))

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

    async def observe_pressure_band(self, approver_id: str, band: str) -> int:
        """Bump the consecutive-observation counter for one metric band.

        A new band for this approver resets every other band's counter to
        zero (a fresh run starts counting over), matching the semantics the
        policy engine previously implemented with a module-level dict. This
        version is lock-protected and scoped to the store instance.
        """
        async with self._lock:
            bands = self._consecutive_observations[approver_id]
            bands[band] = bands.get(band, 0) + 1
            for other_band in list(bands):
                if other_band != band:
                    bands[other_band] = 0
            return bands[band]

    async def should_run_agent(
        self, approver_id: str, min_interval_seconds: float, now: datetime
    ) -> bool:
        """Throttle sustained-pressure agent re-invocation to roughly once
        per ``min_interval_seconds``, using request arrivals as the clock
        tick instead of a separate scheduler/poller process."""
        now = self._as_utc(now)
        async with self._lock:
            last = self._last_agent_run.get(approver_id)
            if last is not None and (now - last).total_seconds() < min_interval_seconds:
                return False
            self._last_agent_run[approver_id] = now
            return True


# Shared by all routers in the local single-process deployment.
state_store = StateStore()
