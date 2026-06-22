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

    # Auth. "dev_header" (default) trusts an X-Account-Id header — for tests/local
    # only. "session" requires a password login and a signed-cookie session, and
    # maps the logged-in user to the single tenant account below.
    auth_mode: str = os.environ.get("AUTH_MODE", "dev_header")
    session_secret: str = os.environ.get("SESSION_SECRET", "dev-insecure-secret")
    login_password: str = os.environ.get("LOGIN_PASSWORD", "")

    # Tenant #1 bootstrap (used in session mode).
    tenant_owner_user_id: str = os.environ.get("TENANT_OWNER_USER_ID", "tenant-1")
    tenant_name: str = os.environ.get("TENANT_NAME", "FLUXO")

    def __post_init__(self) -> None:
        if self.backend == "postgres" and not self.database_url:
            raise ValueError("LEADCENTER_BACKEND=postgres requires DATABASE_URL")
        if self.auth_mode == "session":
            if not self.login_password:
                raise ValueError("AUTH_MODE=session requires LOGIN_PASSWORD")
            if self.session_secret == "dev-insecure-secret":
                raise ValueError("AUTH_MODE=session requires a real SESSION_SECRET")


def load_config() -> Config:
    """Build a Config from the current environment."""
    return Config()
