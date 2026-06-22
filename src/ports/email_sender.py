"""EmailSenderPort — deliver one email. Start with Resend/Postmark; swappable to
Gmail API/SES behind this port. Implementations raise on failure so the caller
never bills a send that didn't happen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SentMessage:
    provider_id: str
    state: str  # "sent" | "queued" — the provider's accepted state


class EmailSenderPort(Protocol):
    def send(
        self, *, to: str, subject: str, body: str, from_name: str, from_email: str
    ) -> SentMessage: ...
