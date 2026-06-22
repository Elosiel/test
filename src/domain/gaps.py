"""Primary-gap derivation — pure, from data we already hold (no enrichment crawl yet).

Returns a short, human-readable gap used for gap-first pitching when a business has
no hot signal. Deterministic priority order; None when nothing obvious stands out.
"""
from __future__ import annotations

from src.domain.entities import Business

THIN_REVIEWS = 10
POOR_RATING = 3.5


def primary_gap(business: Business) -> str | None:
    if not business.website:
        return "no website"
    if business.rating is not None and business.rating <= POOR_RATING:
        return "poor online reputation"
    if business.review_count is not None and business.review_count < THIN_REVIEWS:
        return "thin review presence"
    return None
