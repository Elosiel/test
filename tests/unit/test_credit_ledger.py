"""P0 — credit-ledger invariants. The financial source of truth.

Covers: derived balance, overdraft rejection, transactional rollback (never bill
failed work), tenant isolation of balances, and balance_after consistency.
"""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.application import credits
from src.domain.entities import new_id
from src.domain.errors import InsufficientCreditsError


def _uow_factory(store):
    return lambda: MemoryUnitOfWork(store)


def test_balance_is_derived_from_ledger(store, account_id):
    uow_factory = _uow_factory(store)
    with uow_factory() as uow:
        credits.grant(uow, account_id, 30, reason="seed")
        uow.commit()
    with uow_factory() as uow:
        credits.spend(uow, account_id, 10, reason="scan")
        uow.commit()
    with uow_factory() as uow:
        assert credits.balance(uow, account_id) == 20


def test_spend_rejected_when_it_would_go_negative(store, account_id):
    uow_factory = _uow_factory(store)
    with uow_factory() as uow:
        credits.grant(uow, account_id, 5, reason="seed")
        uow.commit()
    with uow_factory() as uow:
        with pytest.raises(InsufficientCreditsError):
            credits.spend(uow, account_id, 6, reason="scan")


def test_uncommitted_transaction_does_not_change_balance(store, account_id):
    """Rollback semantics: staged writes never reach the store without commit."""
    uow_factory = _uow_factory(store)
    with uow_factory() as uow:
        credits.grant(uow, account_id, 100, reason="seed")
        uow.commit()
    # Open a tx, spend, but DON'T commit -> on exit it rolls back.
    with uow_factory() as uow:
        credits.spend(uow, account_id, 40, reason="scan")
        # no commit
    with uow_factory() as uow:
        assert credits.balance(uow, account_id) == 100


def test_failure_mid_transaction_rolls_back_the_spend(store, account_id):
    """Never bill failed work: an exception after a spend discards the spend."""
    uow_factory = _uow_factory(store)
    with uow_factory() as uow:
        credits.grant(uow, account_id, 50, reason="seed")
        uow.commit()
    with pytest.raises(RuntimeError):
        with uow_factory() as uow:
            credits.spend(uow, account_id, 20, reason="scan")
            raise RuntimeError("downstream work failed")  # uow exits without commit
    with uow_factory() as uow:
        assert credits.balance(uow, account_id) == 50


def test_balances_are_isolated_per_account(store):
    uow_factory = _uow_factory(store)
    a, b = new_id(), new_id()
    with uow_factory() as uow:
        credits.grant(uow, a, 10, reason="seed")
        credits.grant(uow, b, 99, reason="seed")
        uow.commit()
    with uow_factory() as uow:
        assert credits.balance(uow, a) == 10
        assert credits.balance(uow, b) == 99


def test_non_positive_amounts_rejected(store, account_id):
    uow_factory = _uow_factory(store)
    with uow_factory() as uow:
        with pytest.raises(ValueError):
            credits.grant(uow, account_id, 0, reason="x")
        with pytest.raises(ValueError):
            credits.spend(uow, account_id, -1, reason="x")


@given(
    grant=st.integers(min_value=1, max_value=10_000),
    spends=st.lists(st.integers(min_value=1, max_value=500), max_size=40),
)
def test_property_balance_equals_sum_of_deltas(grant, spends):
    """For any grant + sequence of (accepted) spends, balance == sum of deltas and
    balance_after on the last entry matches the derived balance.
    """
    store = MemoryStore()
    account = new_id()
    uow_factory = _uow_factory(store)
    with uow_factory() as uow:
        credits.grant(uow, account, grant, reason="seed")
        uow.commit()

    expected = grant
    for amount in spends:
        with uow_factory() as uow:
            if credits.balance(uow, account) < amount:
                continue  # overdraft would be rejected; skip to keep the sequence valid
            entry = credits.spend(uow, account, amount, reason="scan")
            uow.commit()
            expected -= amount
            assert entry.balance_after == expected

    with uow_factory() as uow:
        assert credits.balance(uow, account) == expected
        assert expected == sum(e.delta for e in store.ledger if e.account_id == account)
