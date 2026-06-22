"""Opportunity scoring — "does this business have approachable pain?"

Pure, deterministic, 0-100. v1 heuristic (explicitly tunable; calibration is an
OPEN item in ARCHITECTURE.md):

- Vibe  — reputation pain. A lower rating means more room to help: (5 - rating)/4.
- Density — is it an established business worth pitching? review_count vs a cap.
- Vigor — recency/activity. DEFERRED to step 3 (the fresh_pain SIGNAL needs
  per-review timestamps we don't hold yet). We do NOT fabricate recency data, so
  Vigor contributes nothing in v1 and the blend is over Vibe + Density only.

Missing inputs degrade to a neutral 50 for that component rather than punishing a
lead for data we simply don't have.
"""
from __future__ import annotations

# Established-business ceiling: review counts at/above this are "max density".
DENSITY_CAP = 100

# v1 sub-weights within Opportunity (Vigor deferred -> weight 0).
_VIBE_WEIGHT = 0.6
_DENSITY_WEIGHT = 0.4


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def opportunity_score(
    rating: float | None,
    review_count: int | None,
    *,
    has_website: bool,
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

    score = _VIBE_WEIGHT * vibe + _DENSITY_WEIGHT * density

    # A business with no website is a slightly softer target (more gaps to pitch).
    if not has_website:
        score += 5.0

    return _clamp(score)
