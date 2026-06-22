"""Unit tests for the Opportunity component (pure, deterministic)."""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.domain.opportunity import opportunity_score


def test_lower_rating_means_more_opportunity():
    low = opportunity_score(1.0, 50, has_website=True)
    high = opportunity_score(5.0, 50, has_website=True)
    assert low > high


def test_more_reviews_means_more_density():
    few = opportunity_score(3.0, 1, has_website=True)
    many = opportunity_score(3.0, 100, has_website=True)
    assert many > few


def test_missing_inputs_are_neutral_not_punished():
    score = opportunity_score(None, None, has_website=True)
    assert 40 <= score <= 60  # both components neutral ~50


def test_no_website_nudges_score_up():
    with_site = opportunity_score(3.0, 50, has_website=True)
    without = opportunity_score(3.0, 50, has_website=False)
    assert without > with_site


def test_review_count_caps_out():
    at_cap = opportunity_score(3.0, 100, has_website=True)
    over_cap = opportunity_score(3.0, 5000, has_website=True)
    assert at_cap == over_cap


@given(
    rating=st.one_of(st.none(), st.floats(min_value=0, max_value=5)),
    reviews=st.one_of(st.none(), st.integers(min_value=0, max_value=1_000_000)),
    has_website=st.booleans(),
)
def test_always_within_bounds(rating, reviews, has_website):
    assert 0 <= opportunity_score(rating, reviews, has_website=has_website) <= 100
