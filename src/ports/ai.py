"""AIPort — generation only (the LLM is used only at the edges). Start adapter:
Anthropic (Haiku); swappable to any LLM behind this port. The core never imports a
vendor SDK.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PitchBrief:
    """Everything the model needs to draft a first-touch email for one lead.
    ``mode`` is "signal" when there is a hot signal, else "gap".
    """
    business_name: str
    category: str | None
    mode: str
    hot_signal: bool
    fresh_pain: dict | None
    primary_gap: str | None
    rating: float | None
    review_count: int | None


class AIPort(Protocol):
    def generate_pitch(self, brief: PitchBrief) -> str:
        """Return a <=150-word first email: signal-first when a hot signal exists,
        else gap-first. Differential positioning. Raises on failure (never returns
        a silent fallback presented as a real draft).
        """
        ...
