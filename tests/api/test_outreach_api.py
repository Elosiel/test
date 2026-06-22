"""API: POST /leads/{id}/contact (gated, debits) and the public GET /unsubscribe."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.ai.fake_ai_adapter import FakeAI
from src.adapters.data.fake_data_provider import FakeDataProvider
from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.adapters.email.fake_finder import FakeEmailFinder
from src.adapters.email.fake_sender import FakeEmailSender
from src.application import credits
from src.config import Config
from src.delivery.api.app import create_app
from src.delivery.deps import Deps
from src.domain.entities import new_id


def _client(store, **config_overrides):
    config = Config(backend="memory", physical_address="123 Main St, Austin TX",
                    **config_overrides)
    deps = Deps(
        config=config,
        data_provider=FakeDataProvider(),
        ai=FakeAI(),
        uow_factory_for=lambda _a: (lambda: MemoryUnitOfWork(store)),
        email_finder=FakeEmailFinder(),
        email_sender=FakeEmailSender(),
    )
    return TestClient(create_app(deps))


@pytest.fixture
def account():
    return new_id()


def _seed(client, account):
    client.post("/scans", headers={"X-Account-Id": account},
                json={"niche": "plumbers", "city": "austin", "limit": 3, "confirmed": True})
    lead_id = client.get("/leads", headers={"X-Account-Id": account}).json()[0]["id"]
    client.post(f"/leads/{lead_id}/pitch", headers={"X-Account-Id": account})
    return lead_id


def test_contact_disabled_returns_403():
    store, acct = MemoryStore(), new_id()
    with MemoryUnitOfWork(store) as uow:
        credits.grant(uow, acct, 50, reason="seed")
        uow.commit()
    client = _client(store, outreach_enabled=False)
    lead_id = _seed(client, acct)
    r = client.post(f"/leads/{lead_id}/contact", headers={"X-Account-Id": acct})
    assert r.status_code == 403


def test_contact_enabled_sends_and_debits():
    store, acct = MemoryStore(), new_id()
    with MemoryUnitOfWork(store) as uow:
        credits.grant(uow, acct, 50, reason="seed")
        uow.commit()
    client = _client(store, outreach_enabled=True)
    lead_id = _seed(client, acct)

    r = client.post(f"/leads/{lead_id}/contact", headers={"X-Account-Id": acct})
    assert r.status_code == 200
    assert r.json()["status"] == "contacted"
    # 50 - 3 (scan) - 1 (pitch) - 1 (send) = 45
    bal = client.get("/balance", headers={"X-Account-Id": acct}).json()["balance"]
    assert bal == 45


def test_unsubscribe_is_public_and_suppresses():
    store, acct = MemoryStore(), new_id()
    with MemoryUnitOfWork(store) as uow:
        credits.grant(uow, acct, 50, reason="seed")
        uow.commit()
    client = _client(store, outreach_enabled=True)
    lead_id = _seed(client, acct)

    # No auth header — must still work (CAN-SPAM).
    u = client.get("/unsubscribe", params={"email": "info@example.test", "account": acct})
    assert u.status_code == 200
    with MemoryUnitOfWork(store) as uow:
        assert uow.suppression.is_suppressed(acct, "info@example.test")
