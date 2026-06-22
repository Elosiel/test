"""Domain entities. Plain, framework-free dataclasses keyed to the data model in
ARCHITECTURE.md. Every tenant-owned entity carries an ``account_id`` — the column
that RLS scopes on at the database.

Scoring/signal/outreach fields exist on ``Lead`` to match the schema, but the v1
spine leaves them at their defaults; they are populated in later build steps.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class LeadStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    REPLIED = "replied"
    BOOKED = "booked"


class MessageDirection(str, Enum):
    OUT = "out"
    IN = "in"


class MessageState(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    BOUNCED = "bounced"
    REPLIED = "replied"


@dataclass(frozen=True)
class Account:
    owner_user_id: str
    name: str
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True)
class Persona:
    account_id: str
    name: str
    target_category: str
    geo: str
    keywords: list[str] = field(default_factory=list)
    size_hint: str | None = None
    notes: str | None = None
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True)
class Territory:
    account_id: str
    persona_id: str
    niche: str
    city: str
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True)
class Run:
    account_id: str
    territory_id: str
    limit: int
    cost_credits: int
    summary: dict = field(default_factory=dict)
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True)
class Review:
    """A single review, as carried on a Business for signal/scoring. ``age_days`` is
    how long ago it was posted; ``has_owner_reply`` whether the business answered it.
    """
    rating: float
    age_days: int
    has_owner_reply: bool = False


@dataclass(frozen=True)
class Business:
    """A value object returned by the DataProviderPort, before it becomes a Lead.
    Carries no ``account_id`` — it is provider data, not yet tenant-owned.
    """
    name: str
    category: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    review_count: int | None = None
    source: str = "unknown"
    external_id: str | None = None
    reviews: list[Review] = field(default_factory=list)


@dataclass(frozen=True)
class Lead:
    account_id: str
    run_id: str
    name: str
    category: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    email: str | None = None
    email_verified: bool = False
    rating: float | None = None
    review_count: int | None = None
    # Scoring (build-order step 2).
    opportunity: int = 0
    fit: int = 0
    confidence: int = 0
    rank: float = 0.0
    # Signal / pitch (steps 3-4).
    primary_gap: str | None = None
    hot_signal: bool = False
    fresh_pain: dict | None = None
    pitch: str | None = None
    # Lifecycle.
    status: LeadStatus = LeadStatus.NEW
    source: str = "unknown"
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True)
class CreditLedgerEntry:
    """Append-only. ``delta`` is positive for grants, negative for spends. Balance
    is *derived* as SUM(delta) for an account — never a mutable counter.
    ``balance_after`` is stored for audit only; the sum is the source of truth.
    """
    account_id: str
    delta: int
    reason: str
    balance_after: int
    stripe_event_id: str | None = None
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True)
class Message:
    """An outreach message (out) or, later, an inbound reply (in)."""
    account_id: str
    lead_id: str
    direction: MessageDirection
    subject: str
    body: str
    state: MessageState = MessageState.QUEUED
    provider_id: str | None = None
    sent_at: datetime | None = None
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=now)


@dataclass(frozen=True)
class Suppression:
    """An opt-out or hard bounce. Checked before every send; honored forever.
    ``email_or_domain`` suppresses either a specific address or a whole domain.
    """
    account_id: str
    email_or_domain: str
    reason: str
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=now)
