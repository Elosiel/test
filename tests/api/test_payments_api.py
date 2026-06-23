"""API: GET /packs, POST /checkout, and the idempotent POST /webhooks/stripe."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src.adapters.ai.fake_ai_adapter import FakeAI
from src.adapters.data.fake_data_provider import FakeDataProvider
from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.adapters.payments.fake_payments import FakePayments
from src.application import credits
from src.application.payments import ensure_packs
from src.config import Config
from src.delivery.api.app import create_app
from src.delivery.deps import Deps
from src.domain.entities import new_id


@pytest.fixture
def client_account_store():
    store = MemoryStore()
    account = new_id()
    with MemoryUnitOfWork(store) as uow:
        credits.grant(uow, account, 10, reason="seed")
        ensure_packs(uow)
        uow.commit()
    deps = Deps(
        config=Config(backend="memory"),
        data_provider=FakeDataProvider(),
        ai=FakeAI(),
        uow_factory_for=lambda _a: (lambda: MemoryUnitOfWork(store)),
        payments=FakePayments(),
    )
    return TestClient(create_app(deps)), account, store


def test_list_packs(client_account_store):
    client, _, _ = client_account_store
    r = client.get("/packs")
    assert r.status_code == 200
    assert len(r.json()) >= 1
    assert {"id", "name", "credits", "price_cents"} <= r.json()[0].keys()


def test_checkout_returns_url(client_account_store):
    client, account, _ = client_account_store
    pack_id = client.get("/packs").json()[0]["id"]
    r = client.post("/checkout", headers={"X-Account-Id": account},
                    json={"pack_id": pack_id})
    assert r.status_code == 200
    assert r.json()["checkout_url"]


def test_webhook_grants_then_idempotent(client_account_store):
    client, account, store = client_account_store
    pack = client.get("/packs").json()[0]
    payload = json.dumps({
        "id": "evt_api_1", "type": "checkout.session.completed",
        "account_id": account, "pack_id": pack["id"],
    })

    r1 = client.post("/webhooks/stripe", content=payload)
    assert r1.status_code == 200 and r1.json()["granted"] is True

    r2 = client.post("/webhooks/stripe", content=payload)
    assert r2.json()["granted"] is False  # replay no-op

    with MemoryUnitOfWork(store) as uow:
        # 10 seed + pack credits, granted exactly once.
        assert credits.balance(uow, account) == 10 + pack["credits"]
