"""Unit tests for the Fit component (pure, deterministic)."""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from src.domain.entities import Business, Persona
from src.domain.fit import fit_score


def _persona(**overrides) -> Persona:
    base = dict(name="p", target_category="plumbers", geo="austin", keywords=[], size_hint=None)
    base.update(overrides)
    return Persona(account_id="a", **base)


def _business(**overrides) -> Business:
    base = dict(name="Acme", category="plumbers", address="1 St, Austin", review_count=20)
    base.update(overrides)
    return Business(**base)


def test_category_match_beats_mismatch():
    match = fit_score(_business(category="plumbers"), _persona(target_category="plumbers"))
    miss = fit_score(_business(category="florists"), _persona(target_category="plumbers"))
    assert match > miss


def test_geo_match_adds_points():
    here = fit_score(_business(address="1 St, Austin"), _persona(geo="austin"))
    elsewhere = fit_score(_business(address="1 St, Seattle"), _persona(geo="austin"))
    assert here > elsewhere


def test_keyword_hit_adds_points():
    hit = fit_score(_business(name="24/7 Emergency Plumbers"), _persona(keywords=["emergency"]))
    no_hit = fit_score(_business(name="Quiet Plumbers"), _persona(keywords=["emergency"]))
    assert hit > no_hit


def test_size_band_match_adds_points():
    in_band = fit_score(_business(review_count=20), _persona(size_hint="small"))
    out_band = fit_score(_business(review_count=5000), _persona(size_hint="small"))
    assert in_band > out_band


def test_empty_persona_is_neutral():
    score = fit_score(_business(), Persona(account_id="a", name="p", target_category="",
                                           geo="", keywords=[], size_hint=None))
    # All four components neutralized at half -> ~ (20+10+10+10)
    assert 40 <= score <= 60


@given(
    category=st.one_of(st.none(), st.text(max_size=20)),
    reviews=st.one_of(st.none(), st.integers(min_value=0, max_value=1_000_000)),
)
def test_always_within_bounds(category, reviews):
    b = Business(name="X", category=category, address="somewhere", review_count=reviews)
    p = _persona(keywords=["x"], size_hint="medium")
    assert 0 <= fit_score(b, p) <= 100
