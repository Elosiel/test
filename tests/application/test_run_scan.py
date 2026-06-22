"""P0 — RunScan use case: the vertical slice that proves the spine.

Finds N businesses -> writes N leads -> spends N credits, atomically, with
confirm-before-spend and cap enforcement. As of step 2, written leads are scored
and ranked.
"""
from __future__ import annotations

import pytest

from src.adapters.data.fake_data_provider import FakeDataProvider
from src.application import credits
from src.application.run_scan import run_scan
from src.domain.entities import Business, Persona, Review, Territory
from src.domain.errors import ConfirmationRequiredError, InsufficientCreditsError
from src.domain.scoring import Weights

WEIGHTS = Weights(opportunity=0.5, fit=0.3, confidence=0.2)


def _territory(account_id: str) -> Territory:
    return Territory(account_id=account_id, persona_id="p", niche="plumbers", city="austin")


def _persona(account_id: str, **overrides) -> Persona:
    base = dict(
        name="inline", target_category="plumbers", geo="austin", keywords=[], size_hint=None
    )
    base.update(overrides)
    return Persona(account_id=account_id, **base)


def _run(uow_factory, provider, account_id, **overrides):
    kwargs = dict(
        account_id=account_id,
        territory=_territory(account_id),
        persona=_persona(account_id),
        weights=WEIGHTS,
        limit=10,
        credit_per_lead=1,
        max_leads_per_run=200,
        confirmed=True,
    )
    kwargs.update(overrides)
    return run_scan(uow_factory, provider, **kwargs)


def test_scan_writes_leads_and_spends_credits(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 50)
    result = _run(uow_factory, FakeDataProvider(), account_id)

    assert result.written == 10
    assert result.spent == 10
    with uow_factory() as uow:
        assert credits.balance(uow, account_id) == 40
        assert len(uow.leads.list_for_account(account_id)) == 10


def test_recent_bad_review_yields_hot_signal_and_gap(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 50)

    class HotProvider:
        def search(self, niche, city, limit):
            return [Business(name="Acme", category="plumbers", address="1 St, Austin",
                             website=None, rating=2.5, review_count=4,
                             reviews=[Review(rating=2.0, age_days=3, has_owner_reply=False)])]

    _run(uow_factory, HotProvider(), account_id, limit=1)
    with uow_factory() as uow:
        lead = uow.leads.list_for_account(account_id)[0]
    assert lead.hot_signal is True
    assert lead.fresh_pain and lead.fresh_pain["review_age_days"] == 3
    assert lead.primary_gap == "no website"


def test_written_leads_are_scored_and_ranked(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 50)
    _run(uow_factory, FakeDataProvider(), account_id, limit=5)
    with uow_factory() as uow:
        leads = uow.leads.list_for_account(account_id)
    # Scores were populated (not left at the default 0) and rank is within bounds.
    assert all(0 <= l.rank <= 100 for l in leads)
    assert any(l.opportunity > 0 for l in leads)
    assert any(l.fit > 0 for l in leads)


def test_matching_persona_scores_higher_fit_than_mismatch(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 50)

    class OneProvider:
        def search(self, niche, city, limit):
            return [Business(name="Acme", category="plumbers", address="1 St, Austin",
                             review_count=20, rating=3.0, website="https://x.test")]

    _run(uow_factory, OneProvider(), account_id, limit=1,
         persona=_persona(account_id, target_category="plumbers", geo="austin"))
    with uow_factory() as uow:
        good_fit = uow.leads.list_for_account(account_id)[0].fit

    other = Persona(account_id=account_id, name="x", target_category="florists",
                    geo="seattle", keywords=[], size_hint=None)
    # New account avoids mixing leads.
    from src.domain.entities import new_id
    acct2 = new_id()
    grant_credits(acct2, 50)
    _run(uow_factory, OneProvider(), acct2, limit=1, persona=other,
         territory=_territory(acct2))
    with uow_factory() as uow:
        bad_fit = uow.leads.list_for_account(acct2)[0].fit

    assert good_fit > bad_fit


def test_unconfirmed_scan_raises_with_estimate(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 50)
    with pytest.raises(ConfirmationRequiredError) as exc:
        _run(uow_factory, FakeDataProvider(), account_id, limit=7, confirmed=False)
    assert exc.value.estimated_cost == 7


def test_insufficient_balance_writes_nothing_and_skips_provider(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 3)

    class ExplodingProvider:
        def search(self, *a, **k):
            raise AssertionError("provider must not be called when balance is short")

    with pytest.raises(InsufficientCreditsError):
        _run(uow_factory, ExplodingProvider(), account_id, limit=10)

    with uow_factory() as uow:
        assert credits.balance(uow, account_id) == 3
        assert uow.leads.list_for_account(account_id) == []


def test_limit_over_cap_rejected(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 1000)
    with pytest.raises(ValueError):
        _run(uow_factory, FakeDataProvider(), account_id, limit=201)


def test_credit_per_lead_multiplier_is_applied(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 50)

    class TwoProvider:
        def search(self, niche, city, limit):
            return [Business(name=f"b{i}") for i in range(limit)]

    result = _run(uow_factory, TwoProvider(), account_id, limit=5, credit_per_lead=2)
    assert result.spent == 10
    with uow_factory() as uow:
        assert credits.balance(uow, account_id) == 40
