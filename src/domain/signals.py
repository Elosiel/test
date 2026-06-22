"""Signal detection — pure functions over review data.

v1 ships a single signal: ``fresh_pain``. A business has fresh pain when it has a
review that is recent (<= FRESH_DAYS old), low (<= MAX_RATING stars), and that the
owner has NOT replied to — a timely, approachable opening to reach out about.

Detectors are standalone pure functions so new signals (new GBP, hiring, website
tech change) can be added later without touching the pipeline.
"""
from __future__ import annotations

from src.domain.entities import Review

FRESH_DAYS = 14
MAX_RATING = 3


def detect_fresh_pain(reviews: list[Review]) -> dict | None:
    """Return a summary of the most recent qualifying review, or None.

    Qualifying = age_days <= FRESH_DAYS and rating <= MAX_RATING and not answered.
    Picks the freshest (lowest age_days) qualifying review when several qualify.
    """
    qualifying = [
        r
        for r in reviews
        if r.age_days <= FRESH_DAYS and r.rating <= MAX_RATING and not r.has_owner_reply
    ]
    if not qualifying:
        return None
    worst = min(qualifying, key=lambda r: (r.age_days, r.rating))
    return {
        "review_age_days": worst.age_days,
        "rating": worst.rating,
        "unanswered": True,
    }
