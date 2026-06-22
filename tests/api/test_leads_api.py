"""API tests for the Radar feed: GET /leads returns ranked, scored leads, scoped
to the authed account.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.data.fake_data_provider import FakeDataProvider
from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.application import credits
from src.config import Config
from src.delivery.api.app import Deps, create_app
from src.domain.entities import new_id


@pytest.fixture
def client_and_accounts():
    store = MemoryStore()
    a, b = new_id(), new_id()
    for acct in (a, b):
        with MemoryUnitOfWork(store) as uow:
            credits.grant(uow, acct, 50, reason="test:seed")
            uow.commit()
    deps = Deps(
        config=Config(backend="memory"),
        data_provider=FakeDataProvider(),
        uow_factory_for=lambda _acct: (lambda: MemoryUnitOfWork(store)),
    )
    return TestClient(create_app(deps)), a, b


def _scan(client, account, **body):
    payload = {"niche": "plumbers", "city": "austin", "limit": 5, "confirmed": True}
    payload.update(body)
    return client.post("/scans", headers={"X-Account-Id": account}, json=payload)


def test_leads_requires_account_header(client_and_accounts):
    client, _, _ = client_and_accounts
    assert client.get("/leads").status_code == 401


def test_leads_returned_ranked_with_scores(client_and_accounts):
    client, a, _ = client_and_accounts
    assert _scan(client, a).status_code == 200

    r = client.get("/leads", headers={"X-Account-Id": a})
    assert r.status_code == 200
    leads = r.json()
    assert len(leads) == 5
    # Descending rank order.
    ranks = [l["rank"] for l in leads]
    assert ranks == sorted(ranks, reverse=True)
    # Score fields are present and populated.
    assert all({"opportunity", "fit", "confidence", "rank"} <= l.keys() for l in leads)


def test_leads_are_account_isolated(client_and_accounts):
    client, a, b = client_and_accounts
    _scan(client, a)
    # Account b has run no scan -> sees nothing of a's leads.
    r = client.get("/leads", headers={"X-Account-Id": b})
    assert r.json() == []
