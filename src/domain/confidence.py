"""Confidence scoring — "how complete/trustworthy is the data we hold?"

Pure, deterministic, 0-100. Drives the "never auto-send a low-confidence lead" gate
that is enforced at send time in step 5; here we only compute and store it.

v1 component points (tunable), capped at 100:
  has website            25
  has email              25
  email verified         20   (only meaningful when an email exists)
  has rating             10
  enough reviews         20   (review_count >= REVIEW_FLOOR)
"""
from __future__ import annotations

REVIEW_FLOOR = 5

_WEBSITE = 25
_EMAIL = 25
_EMAIL_VERIFIED = 20
_RATING = 10
_REVIEWS = 20


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def confidence_score(
    *,
    has_website: bool,
    has_email: bool,
    email_verified: bool,
    rating: float | None,
    review_count: int | None,
) -> int:
    score = 0.0
    if has_website:
        score += _WEBSITE
    if has_email:
        score += _EMAIL
        if email_verified:
            score += _EMAIL_VERIFIED
    if rating is not None:
        score += _RATING
    if review_count is not None and review_count >= REVIEW_FLOOR:
        score += _REVIEWS
    return _clamp(score)
