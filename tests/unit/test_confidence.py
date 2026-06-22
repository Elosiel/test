"""Unit tests for the Confidence component (pure, deterministic)."""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from src.domain.confidence import confidence_score


def test_more_complete_data_means_higher_confidence():
    bare = confidence_score(has_website=False, has_email=False, email_verified=False,
                            rating=None, review_count=None)
    full = confidence_score(has_website=True, has_email=True, email_verified=True,
                            rating=4.0, review_count=50)
    assert full > bare
    assert full == 100
    assert bare == 0


def test_email_verified_only_counts_when_email_present():
    # email_verified=True but has_email=False must not award the verified bonus.
    score = confidence_score(has_website=False, has_email=False, email_verified=True,
                             rating=None, review_count=None)
    assert score == 0


def test_review_floor_must_be_met():
    below = confidence_score(has_website=False, has_email=False, email_verified=False,
                             rating=None, review_count=1)
    at = confidence_score(has_website=False, has_email=False, email_verified=False,
                          rating=None, review_count=5)
    assert below == 0
    assert at == 20


@given(
    has_website=st.booleans(),
    has_email=st.booleans(),
    email_verified=st.booleans(),
    rating=st.one_of(st.none(), st.floats(min_value=0, max_value=5)),
    review_count=st.one_of(st.none(), st.integers(min_value=0, max_value=10_000)),
)
def test_always_within_bounds(has_website, has_email, email_verified, rating, review_count):
    assert 0 <= confidence_score(
        has_website=has_website, has_email=has_email, email_verified=email_verified,
        rating=rating, review_count=review_count,
    ) <= 100
