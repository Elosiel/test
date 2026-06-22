"""fresh_pain truth table — pure, deterministic."""
from __future__ import annotations

from src.domain.entities import Review
from src.domain.signals import detect_fresh_pain


def test_recent_low_unanswered_review_fires():
    fp = detect_fresh_pain([Review(rating=2.0, age_days=5, has_owner_reply=False)])
    assert fp is not None
    assert fp["review_age_days"] == 5
    assert fp["unanswered"] is True


def test_answered_review_does_not_fire():
    assert detect_fresh_pain([Review(rating=1.0, age_days=3, has_owner_reply=True)]) is None


def test_old_review_does_not_fire():
    # 15 days is past the 14-day window.
    assert detect_fresh_pain([Review(rating=1.0, age_days=15, has_owner_reply=False)]) is None


def test_age_boundary_14_days_fires():
    assert detect_fresh_pain([Review(rating=3.0, age_days=14, has_owner_reply=False)]) is not None


def test_high_rating_does_not_fire():
    # 4 stars is above the <=3 threshold.
    assert detect_fresh_pain([Review(rating=4.0, age_days=2, has_owner_reply=False)]) is None


def test_no_reviews_does_not_fire():
    assert detect_fresh_pain([]) is None


def test_picks_freshest_qualifying_review():
    fp = detect_fresh_pain([
        Review(rating=3.0, age_days=12, has_owner_reply=False),
        Review(rating=1.0, age_days=2, has_owner_reply=False),
    ])
    assert fp["review_age_days"] == 2
