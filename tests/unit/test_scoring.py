"""Unit tests for score aggregation (blend + score_business)."""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.domain.entities import Business, Persona
from src.domain.scoring import ScoreResult, Weights, blend, score_business


def test_blend_is_weighted_average():
    w = Weights(opportunity=0.5, fit=0.3, confidence=0.2)
    assert blend(100, 0, 0, w) == 50.0
    assert blend(0, 100, 0, w) == 30.0
    assert blend(0, 0, 100, w) == 20.0


def test_blend_normalizes_unnormalized_weights():
    # Weights that don't sum to 1 still produce a 0-100 rank.
    w = Weights(opportunity=5, fit=3, confidence=2)
    assert blend(100, 100, 100, w) == 100.0
    assert 0 <= blend(80, 40, 10, w) <= 100


def test_blend_rejects_nonpositive_weight_sum():
    with pytest.raises(ValueError):
        blend(50, 50, 50, Weights(opportunity=0, fit=0, confidence=0))


def test_score_business_populates_all_components():
    b = Business(name="Acme", category="plumbers", address="1 St, Austin",
                 rating=3.0, review_count=20, website="https://x.test")
    p = Persona(account_id="a", name="p", target_category="plumbers", geo="austin",
                keywords=[], size_hint="small")
    result = score_business(b, p, Weights(0.5, 0.3, 0.2))
    assert isinstance(result, ScoreResult)
    assert result.opportunity > 0
    assert result.fit > 0
    assert 0 <= result.rank <= 100


@given(
    rating=st.one_of(st.none(), st.floats(min_value=0, max_value=5)),
    reviews=st.one_of(st.none(), st.integers(min_value=0, max_value=10_000)),
    website=st.one_of(st.none(), st.just("https://x.test")),
)
def test_rank_always_within_bounds(rating, reviews, website):
    b = Business(name="X", category="plumbers", address="Austin",
                 rating=rating, review_count=reviews, website=website)
    p = Persona(account_id="a", name="p", target_category="plumbers", geo="austin",
                keywords=["x"], size_hint="medium")
    result = score_business(b, p, Weights(0.5, 0.3, 0.2))
    assert 0 <= result.rank <= 100
