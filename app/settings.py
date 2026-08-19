from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class Settings:
    database_url: str = os.getenv("WEIR_DATABASE_URL", "sqlite:///./data/weir.db")
    admin_api_key: str = os.getenv("WEIR_ADMIN_API_KEY", "dev-admin-key")
    agent_mode: str = os.getenv("WEIR_AGENT_MODE", "offline")
    policy_state_consecutive_samples: int = int(os.getenv("POLICY_STATE_CONSECUTIVE_SAMPLES", "2"))
    policy_state_hysteresis_pct: float = float(os.getenv("POLICY_STATE_HYSTERESIS_PCT", "10"))
    threshold_elevated_ms: int = int(os.getenv("WEIR_THRESHOLD_ELEVATED_MS", "1000"))
    threshold_critical_ms: int = int(os.getenv("WEIR_THRESHOLD_CRITICAL_MS", "3000"))

