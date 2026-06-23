"""Deterministic PaymentsPort. Honesty rule: charges nothing. ``create_checkout``
returns a stub URL; ``parse_event`` JSON-decodes a webhook body into a WebhookEvent
(no signature to verify — the real Stripe adapter does that). Lets the packs ->
checkout -> webhook -> ledger flow run end-to-end and back the tests.

Expected fake webhook body:
    {"id": "<event id>", "type": "checkout.session.completed",
     "account_id": "<uuid>", "pack_id": "<uuid>"}
"""
from __future__ import annotations

import json

from src.domain.entities import Pack, new_id
from src.ports.payments import CheckoutSession, WebhookEvent


class FakePayments:
    def create_checkout(
        self, *, pack: Pack, account_id: str, success_url: str, cancel_url: str
    ) -> CheckoutSession:
        session_id = f"cs_fake_{new_id()}"
        # The fake "hosted page" is just the success URL with the session id attached.
        url = f"{success_url}?session_id={session_id}"
        return CheckoutSession(id=session_id, url=url)

    def parse_event(self, payload: bytes, signature: str | None) -> WebhookEvent | None:
        data = json.loads(payload.decode("utf-8"))
        if data.get("type") != "checkout.session.completed":
            return None
        return WebhookEvent(
            id=data["id"],
            type=data["type"],
            account_id=data["account_id"],
            pack_id=data["pack_id"],
        )
