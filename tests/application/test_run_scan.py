"""P0 — RunScan use case: the vertical slice that proves the spine.

Finds N businesses -> writes N leads -> spends N credits, atomically, with
confirm-before-spend and cap enforcement.
"""
from __future__ import annotations

import pytest

from src.application import credits
from src.application.run_scan import run_scan
from src.domain.entities import Business, Territory
from src.domain.errors import ConfirmationRequiredError, InsufficientCreditsError


def _territory(account_id: str) -> Territory:
    return Territory(account_id=account_id, persona_id="p", niche="plumbers", city="austin")


def test_scan_writes_leads_and_spends_credits(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 50)
    from src.adapters.data.fake_data_provider import FakeDataProvider

    result = run_scan(
        uow_factory,
        FakeDataProvider(),
        account_id=account_id,
        territory=_territory(account_id),
        limit=10,
        credit_per_lead=1,
        max_leads_per_run=200,
        confirmed=True,
    )

    assert result.written == 10
    assert result.spent == 10
    with uow_factory() as uow:
        assert credits.balance(uow, account_id) == 40
        assert len(uow.leads.list_for_account(account_id)) == 10


def test_unconfirmed_scan_raises_with_estimate(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 50)
    from src.adapters.data.fake_data_provider import FakeDataProvider

    with pytest.raises(ConfirmationRequiredError) as exc:
        run_scan(
            uow_factory,
            FakeDataProvider(),
            account_id=account_id,
            territory=_territory(account_id),
            limit=7,
            credit_per_lead=1,
            max_leads_per_run=200,
            confirmed=False,
        )
    assert exc.value.estimated_cost == 7


def test_insufficient_balance_writes_nothing_and_skips_provider(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 3)

    class ExplodingProvider:
        def search(self, *a, **k):
            raise AssertionError("provider must not be called when balance is short")

    with pytest.raises(InsufficientCreditsError):
        run_scan(
            uow_factory,
            ExplodingProvider(),
            account_id=account_id,
            territory=_territory(account_id),
            limit=10,
            credit_per_lead=1,
            max_leads_per_run=200,
            confirmed=True,
        )

    with uow_factory() as uow:
        assert credits.balance(uow, account_id) == 3
        assert uow.leads.list_for_account(account_id) == []


def test_limit_over_cap_rejected(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 1000)
    from src.adapters.data.fake_data_provider import FakeDataProvider

    with pytest.raises(ValueError):
        run_scan(
            uow_factory,
            FakeDataProvider(),
            account_id=account_id,
            territory=_territory(account_id),
            limit=201,
            credit_per_lead=1,
            max_leads_per_run=200,
            confirmed=True,
        )


def test_credit_per_lead_multiplier_is_applied(store, uow_factory, account_id, grant_credits):
    grant_credits(account_id, 50)

    class TwoProvider:
        def search(self, niche, city, limit):
            return [Business(name=f"b{i}") for i in range(limit)]

    result = run_scan(
        uow_factory,
        TwoProvider(),
        account_id=account_id,
        territory=_territory(account_id),
        limit=5,
        credit_per_lead=2,
        max_leads_per_run=200,
        confirmed=True,
    )
    assert result.spent == 10
    with uow_factory() as uow:
        assert credits.balance(uow, account_id) == 40
