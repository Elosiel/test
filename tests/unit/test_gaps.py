"""primary_gap derivation — pure, priority-ordered."""
from __future__ import annotations

from src.domain.entities import Business
from src.domain.gaps import primary_gap


def test_no_website_is_top_priority():
    assert primary_gap(Business(name="X", website=None, rating=4.8, review_count=100)) == "no website"


def test_poor_rating_when_site_present():
    g = primary_gap(Business(name="X", website="https://x.test", rating=3.0, review_count=100))
    assert g == "poor online reputation"


def test_thin_reviews_when_site_and_rating_ok():
    g = primary_gap(Business(name="X", website="https://x.test", rating=4.7, review_count=3))
    assert g == "thin review presence"


def test_no_obvious_gap_returns_none():
    assert primary_gap(
        Business(name="X", website="https://x.test", rating=4.8, review_count=200)
    ) is None
