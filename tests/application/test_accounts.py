"""ensure_tenant must be idempotent: create the account once, grant free credits once."""
from __future__ import annotations

from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.application import credits
from src.application.accounts import ensure_tenant


def _factory(store):
    return lambda: MemoryUnitOfWork(store)


def test_creates_account_and_grants_free_credits_once():
    store = MemoryStore()
    f = _factory(store)

    with f() as uow:
        first = ensure_tenant(uow, "owner-1", "FLUXO", 50)
        uow.commit()
    with f() as uow:
        second = ensure_tenant(uow, "owner-1", "FLUXO", 50)
        uow.commit()

    assert first.id == second.id  # same account returned, not a duplicate
    assert len(store.accounts) == 1
    with f() as uow:
        assert credits.balance(uow, first.id) == 50  # granted once, not twice


def test_zero_free_credits_creates_account_without_grant():
    store = MemoryStore()
    f = _factory(store)
    with f() as uow:
        acct = ensure_tenant(uow, "owner-2", "Acme", 0)
        uow.commit()
    with f() as uow:
        assert credits.balance(uow, acct.id) == 0
    assert store.ledger == []
