"""Deterministic EmailSenderPort. Honesty rule: this does NOT send a real email — it
records the attempt and returns a synthetic provider id so the pipeline works
end-to-end. Real Resend/Postmark adapter swaps in behind this port (and only then,
with a warmed SPF/DKIM/DMARC domain, does anything actually leave the building).
"""
from __future__ import annotations

from src.domain.entities import new_id
from src.ports.email_sender import SentMessage


class FakeEmailSender:
    def __init__(self) -> None:
        # Kept for test introspection; not a delivery guarantee.
        self.sent: list[dict] = []

    def send(
        self, *, to: str, subject: str, body: str, from_name: str, from_email: str
    ) -> SentMessage:
        self.sent.append({"to": to, "subject": subject, "from_email": from_email})
        return SentMessage(provider_id=f"fake-{new_id()}", state="sent")
