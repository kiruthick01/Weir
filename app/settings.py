from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(slots=True)
class Settings:
    """Environment-backed configuration, re-read fresh on every ``Settings()``.

    Every field uses ``default_factory`` rather than a bare ``os.getenv(...)``
    default. A bare default is a Python dataclass footgun here: it would be
    evaluated exactly once, when this module is first imported, so setting an
    env var afterwards (a different test, a different Settings() call in the
    same process) would silently have no effect. ``default_factory`` reads
    the environment at construction time instead, which is what every
    caller of ``Settings()`` actually expects.
    """

    database_url: str = field(default_factory=lambda: os.getenv("WEIR_DATABASE_URL", "sqlite:///./data/weir.db"))
    admin_api_key: str = field(default_factory=lambda: os.getenv("WEIR_ADMIN_API_KEY", "dev-admin-key"))
    agent_mode: str = field(default_factory=lambda: os.getenv("WEIR_AGENT_MODE", "offline"))
    policy_state_consecutive_samples: int = field(default_factory=lambda: int(os.getenv("POLICY_STATE_CONSECUTIVE_SAMPLES", "2")))
    policy_state_hysteresis_pct: float = field(default_factory=lambda: float(os.getenv("POLICY_STATE_HYSTERESIS_PCT", "10")))
    threshold_elevated_ms: int = field(default_factory=lambda: int(os.getenv("WEIR_THRESHOLD_ELEVATED_MS", "1000")))
    threshold_critical_ms: int = field(default_factory=lambda: int(os.getenv("WEIR_THRESHOLD_CRITICAL_MS", "3000")))
    auto_approve_rate_limit_per_hour: int = field(default_factory=lambda: int(os.getenv("WEIR_AUTO_APPROVE_RATE_LIMIT_PER_HOUR", "10")))
    agent_reinvoke_seconds: float = field(default_factory=lambda: float(os.getenv("WEIR_AGENT_REINVOKE_SECONDS", "45")))

