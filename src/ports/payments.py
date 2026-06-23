"""PaymentsPort — checkout + webhook parsing. Start with Stripe; swappable to
Paddle/Lemon Squeezy behind this port. The core never imports a vendor SDK.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.domain.entities import Pack

WEBHOOK_COMPLETED = "checkout.session.completed"


@dataclass(frozen=True)
class CheckoutSession:
    id: str
    url: str


@dataclass(frozen=True)
class WebhookEvent:
    """A parsed, signature-verified payment event. ``account_id``/``pack_id`` come
    from the checkout metadata we set when creating the session.
    """
    id: str
    type: str
    account_id: str
    pack_id: str


class PaymentsPort(Protocol):
    def create_checkout(
        self, *, pack: Pack, account_id: str, success_url: str, cancel_url: str
    ) -> CheckoutSession: ...

    def parse_event(self, payload: bytes, signature: str | None) -> WebhookEvent | None:
        """Verify the signature and parse the event. Returns None for event types we
        don't handle; raises on an invalid signature (never trust an unverified event).
        """
        ...
