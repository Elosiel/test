"""Opportunity scoring — "does this business have approachable pain?"

Pure, deterministic, 0-100. v1 heuristic (explicitly tunable; calibration is an
OPEN item in ARCHITECTURE.md):

- Vibe  — reputation pain. A lower rating means more room to help: (5 - rating)/4.
- Density — is it an established business worth pitching? review_count vs a cap.
- Vigor — recency/activity. The newer the latest review, the more "alive" (and
  reachable) the business is. Computed from the freshest review's age.

Missing inputs degrade to a neutral 50 for that component rather than punishing a
lead for data we simply don't have.
"""
from __future__ import annotations

from src.domain.entities import Review

# Established-business ceiling: review counts at/above this are "max density".
DENSITY_CAP = 100
# Reviews older than this (days) count as no recent activity (Vigor -> 0).
VIGOR_HORIZON_DAYS = 90

# v1 sub-weights within Opportunity (re-normalized now that Vigor is live).
_VIBE_WEIGHT = 0.45
_DENSITY_WEIGHT = 0.35
_VIGOR_WEIGHT = 0.20


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def _vigor(reviews: list[Review] | None) -> float:
    if not reviews:
        return 50.0  # unknown activity -> neutral
    freshest = min(r.age_days for r in reviews)
    if freshest >= VIGOR_HORIZON_DAYS:
        return 0.0
    return (VIGOR_HORIZON_DAYS - freshest) / VIGOR_HORIZON_DAYS * 100.0


def opportunity_score(
    rating: float | None,
    review_count: int | None,
    *,
    has_website: bool,
    reviews: list[Review] | None = None,
) -> int:
    # Vibe: lower rating -> more approachable pain. Neutral when unknown.
    if rating is None:
        vibe = 50.0
    else:
        vibe = (5.0 - max(0.0, min(5.0, rating))) / 4.0 * 100.0

    # Density: more reviews -> more established / worth the pitch. Neutral when unknown.
    if review_count is None:
        density = 50.0
    else:
        density = min(max(review_count, 0), DENSITY_CAP) / DENSITY_CAP * 100.0

    vigor = _vigor(reviews)

    score = _VIBE_WEIGHT * vibe + _DENSITY_WEIGHT * density + _VIGOR_WEIGHT * vigor

    # A business with no website is a slightly softer target (more gaps to pitch).
    if not has_website:
        score += 5.0

    return _clamp(score)
