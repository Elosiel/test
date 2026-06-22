"""Central configuration. Secrets are read here (composition root reads this),
never in domain or application code. Values come from the environment with safe
defaults so the spine runs locally with no setup.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Config:
    # Backend: "memory" (no DB, default) or "postgres".
    backend: str = os.environ.get("LEADCENTER_BACKEND", "memory")
    database_url: str | None = os.environ.get("DATABASE_URL")

    # Credit economics. The spine bills exactly one credit per lead written.
    free_credits: int = _int_env("LEADCENTER_FREE_CREDITS", 50)
    credit_per_lead: int = 1

    # Score-blend weights live here so the deterministic core stays config-driven.
    # (Scoring itself lands in build-order step 2; weights are declared now.)
    weight_opportunity: float = 0.5
    weight_fit: float = 0.3
    weight_confidence: float = 0.2

    # Caps (cost-safety). Enforced by use cases, not the DB.
    max_leads_per_run: int = 200

    def __post_init__(self) -> None:
        if self.backend == "postgres" and not self.database_url:
            raise ValueError("LEADCENTER_BACKEND=postgres requires DATABASE_URL")


def load_config() -> Config:
    """Build a Config from the current environment."""
    return Config()
