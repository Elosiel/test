"""Fit scoring — "how well does this lead match the Persona for this territory?"

Pure, deterministic, 0-100. Additive components against the existing Persona entity
(src/domain/entities.py). Components whose persona field is absent are neutralized:
their points are awarded at half, so a sparse persona neither unfairly punishes nor
inflates a lead.

v1 component ceilings (tunable):
  category match  40
  geo match       20
  keyword hit     20
  size proxy      20
"""
from __future__ import annotations

from src.domain.entities import Business, Persona

_CATEGORY_MAX = 40
_GEO_MAX = 20
_KEYWORD_MAX = 20
_SIZE_MAX = 20

# review_count band expected per size_hint, used as a coarse size proxy.
_SIZE_BANDS: dict[str, tuple[int, int]] = {
    "small": (0, 50),
    "medium": (50, 300),
    "large": (300, 10_000_000),
}


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def fit_score(business: Business, persona: Persona) -> int:
    score = 0.0

    # Category match (case-insensitive substring either direction).
    if persona.target_category:
        cat = (business.category or "").lower()
        target = persona.target_category.lower()
        if cat and (target in cat or cat in target):
            score += _CATEGORY_MAX
    else:
        score += _CATEGORY_MAX / 2  # no target -> neutral

    # Geo match: persona.geo appears in the business address.
    if persona.geo:
        if persona.geo.lower() in (business.address or "").lower():
            score += _GEO_MAX
    else:
        score += _GEO_MAX / 2

    # Keyword hit in name/category/website.
    if persona.keywords:
        haystack = " ".join(
            filter(None, [business.name, business.category, business.website])
        ).lower()
        if any(kw.lower() in haystack for kw in persona.keywords):
            score += _KEYWORD_MAX
    else:
        score += _KEYWORD_MAX / 2

    # Size proxy: does review_count fall in the band implied by size_hint?
    if persona.size_hint and persona.size_hint.lower() in _SIZE_BANDS:
        low, high = _SIZE_BANDS[persona.size_hint.lower()]
        rc = business.review_count
        if rc is not None and low <= rc < high:
            score += _SIZE_MAX
    else:
        score += _SIZE_MAX / 2

    return _clamp(score)
