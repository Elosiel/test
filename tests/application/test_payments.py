"""Packs + the idempotent webhook->ledger grant (the key step-6 invariant)."""
from __future__ import annotations

import json

import pytest

from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.adapters.payments.fake_payments import FakePayments
from src.application import credits
from src.application.payments import (
    DEFAULT_PACKS,
    PackNotFoundError,
    ensure_packs,
    handle_webhook,
    start_checkout,
)
from src.domain.entities import new_id


def _factory(store):
    return lambda: MemoryUnitOfWork(store)


def _factory_for(store):
    return lambda _acct: (lambda: MemoryUnitOfWork(store))


def _seed_packs(store):
    with _factory(store)() as uow:
        ensure_packs(uow)
    with _factory(store)() as uow:
        return uow.packs.list_active()


def _event(account_id, pack_id, event_id="evt_1", type="checkout.session.completed"):
    return json.dumps(
        {"id": event_id, "type": type, "account_id": account_id, "pack_id": pack_id}
    ).encode()


def test_ensure_packs_is_idempotent():
    store = MemoryStore()
    _seed_packs(store)
    _seed_packs(store)  # second call must not duplicate
    assert len(store.packs) == len(DEFAULT_PACKS)


def test_start_checkout_returns_url():
    store = MemoryStore()
    packs = _seed_packs(store)
    session = start_checkout(
        _factory(store), FakePayments(), account_id=new_id(), pack_id=packs[0].id,
        success_url="http://x/ok", cancel_url="http://x/no",
    )
    assert session.url


def test_start_checkout_unknown_pack_raises():
    store = MemoryStore()
    _seed_packs(store)
    with pytest.raises(PackNotFoundError):
        start_checkout(_factory(store), FakePayments(), account_id=new_id(),
                       pack_id="nope", success_url="x", cancel_url="y")


def test_webhook_grants_credits_once():
    store = MemoryStore()
    packs = _seed_packs(store)
    acct = new_id()
    pack = packs[0]

    granted = handle_webhook(_factory_for(store), FakePayments(),
                             _event(acct, pack.id), signature=None)
    assert granted is True
    with _factory(store)() as uow:
        assert credits.balance(uow, acct) == pack.credits


def test_webhook_is_idempotent_on_event_id():
    store = MemoryStore()
    packs = _seed_packs(store)
    acct = new_id()
    pack = packs[0]
    payload = _event(acct, pack.id, event_id="evt_dup")

    first = handle_webhook(_factory_for(store), FakePayments(), payload, signature=None)
    second = handle_webhook(_factory_for(store), FakePayments(), payload, signature=None)

    assert first is True
    assert second is False  # replay is a no-op
    with _factory(store)() as uow:
        assert credits.balance(uow, acct) == pack.credits  # granted exactly once
    purchase_rows = [e for e in store.ledger if e.stripe_event_id == "evt_dup"]
    assert len(purchase_rows) == 1


def test_non_completed_event_ignored():
    store = MemoryStore()
    packs = _seed_packs(store)
    acct = new_id()
    payload = _event(acct, packs[0].id, type="checkout.session.expired")
    assert handle_webhook(_factory_for(store), FakePayments(), payload, signature=None) is False
    with _factory(store)() as uow:
        assert credits.balance(uow, acct) == 0


def test_unknown_pack_in_event_ignored():
    store = MemoryStore()
    _seed_packs(store)
    acct = new_id()
    payload = _event(acct, "ghost-pack")
    assert handle_webhook(_factory_for(store), FakePayments(), payload, signature=None) is False
    with _factory(store)() as uow:
        assert credits.balance(uow, acct) == 0
