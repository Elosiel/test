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

    # Credit economics. The spine bills one credit per lead written, and one per
    # AI-drafted pitch.
    free_credits: int = _int_env("LEADCENTER_FREE_CREDITS", 50)
    credit_per_lead: int = 1
    credit_per_pitch: int = 1

    # AI model id for the real adapter (the fake adapter ignores it). The latest
    # Haiku per ARCHITECTURE.md's AIPort note; verify via the claude-api skill when
    # the Anthropic adapter is built.
    model_id: str = os.environ.get("MODEL_ID", "claude-haiku-4-5")

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

    # Outreach (step 5). Disabled by default — the riskiest subsystem ships behind a
    # flag. A send costs one credit and is refused below this confidence.
    outreach_enabled: bool = os.environ.get("OUTREACH_ENABLED", "").lower() in {"1", "true", "yes"}
    credit_per_send: int = 1
    min_confidence_to_contact: int = 50
    # CAN-SPAM: a real physical postal address and a working unsubscribe are required
    # on every send. Empty physical_address blocks sending (enforced in compose).
    from_name: str = os.environ.get("OUTREACH_FROM_NAME", "FLUXO")
    from_email: str = os.environ.get("OUTREACH_FROM_EMAIL", "")
    physical_address: str = os.environ.get("OUTREACH_PHYSICAL_ADDRESS", "")
    unsubscribe_base_url: str = os.environ.get("OUTREACH_UNSUBSCRIBE_URL", "")

    # Payments (step 6). Webhook secret used by the real Stripe adapter (the fake
    # ignores it). Checkout success/cancel URLs returned to the payment provider.
    stripe_webhook_secret: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    checkout_success_url: str = os.environ.get(
        "CHECKOUT_SUCCESS_URL", "http://localhost:8000/"
    )
    checkout_cancel_url: str = os.environ.get(
        "CHECKOUT_CANCEL_URL", "http://localhost:8000/"
    )

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
