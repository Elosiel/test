"""POST /leads/{id}/pitch — drafts, debits a credit, returns the pitch; 404 unknown."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.ai.fake_ai_adapter import FakeAI
from src.adapters.data.fake_data_provider import FakeDataProvider
from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.application import credits
from src.config import Config
from src.delivery.api.app import create_app
from src.delivery.deps import Deps
from src.domain.entities import new_id


@pytest.fixture
def client_and_account():
    store = MemoryStore()
    account = new_id()
    with MemoryUnitOfWork(store) as uow:
        credits.grant(uow, account, 50, reason="test:seed")
        uow.commit()
    deps = Deps(
        config=Config(backend="memory"),
        data_provider=FakeDataProvider(),
        ai=FakeAI(),
        uow_factory_for=lambda _acct: (lambda: MemoryUnitOfWork(store)),
    )
    return TestClient(create_app(deps)), account


def _first_lead_id(client, account):
    client.post("/scans", headers={"X-Account-Id": account},
                json={"niche": "plumbers", "city": "austin", "limit": 3, "confirmed": True})
    return client.get("/leads", headers={"X-Account-Id": account}).json()[0]["id"]


def test_pitch_drafts_and_debits(client_and_account):
    client, account = client_and_account
    lead_id = _first_lead_id(client, account)

    r = client.post(f"/leads/{lead_id}/pitch", headers={"X-Account-Id": account})
    assert r.status_code == 200
    assert r.json()["pitch"]

    bal = client.get("/balance", headers={"X-Account-Id": account}).json()["balance"]
    # 50 - 3 (scan) - 1 (pitch) = 46
    assert bal == 46


def test_pitch_unknown_lead_404(client_and_account):
    client, account = client_and_account
    r = client.post(f"/leads/{new_id()}/pitch", headers={"X-Account-Id": account})
    assert r.status_code == 404
