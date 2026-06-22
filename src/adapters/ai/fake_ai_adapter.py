"""Deterministic in-process AIPort. Honesty rule: this is a clearly-labelled fake
draft generator, not a real LLM. It lets pitch generation work end-to-end (and backs
the tests) before the Anthropic adapter exists. Output is capped at 150 words to
match the contract the real adapter must honour.
"""
from __future__ import annotations

from src.ports.ai import PitchBrief

MAX_WORDS = 150


def _truncate_words(text: str, limit: int = MAX_WORDS) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit])


class FakeAI:
    def generate_pitch(self, brief: PitchBrief) -> str:
        name = brief.business_name
        if brief.hot_signal and brief.fresh_pain:
            age = brief.fresh_pain.get("review_age_days", "recent")
            opening = (
                f"Hi {name} team — I noticed a {age}-day-old review that hasn't had a "
                f"reply yet. A fast, on-brand response can turn that around and signal "
                f"to future customers that you're on top of feedback."
            )
        else:
            gap = brief.primary_gap or "a few quick wins online"
            opening = (
                f"Hi {name} team — looking at your online presence I spotted {gap}. "
                f"It's a common, fixable gap that's quietly costing you enquiries."
            )
        body = (
            " I help local businesses like yours close that gap in days, not months, "
            "with a clear before/after and no long contracts. Worth a 10-minute call "
            "this week? Reply here and I'll send two times.\n\n— FLUXO"
        )
        return _truncate_words(opening + body)
