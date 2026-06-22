"""API smoke tests for the spine: auth header, confirm-before-spend (402),
and a successful scan that debits the balance.
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
def client_and_account():
    store = MemoryStore()
    account = new_id()
    # Seed credits.
    with MemoryUnitOfWork(store) as uow:
        credits.grant(uow, account, 50, reason="test:seed")
        uow.commit()

    deps = Deps(
        config=Config(backend="memory"),
        data_provider=FakeDataProvider(),
        uow_factory_for=lambda _acct: (lambda: MemoryUnitOfWork(store)),
    )
    return TestClient(create_app(deps)), account


def test_healthz(client_and_account):
    client, _ = client_and_account
    assert client.get("/healthz").json() == {"status": "ok"}


def test_scan_requires_account_header(client_and_account):
    client, _ = client_and_account
    r = client.post("/scans", json={"niche": "plumbers", "city": "austin", "limit": 3, "confirmed": True})
    assert r.status_code == 401


def test_unconfirmed_scan_returns_402_with_estimate(client_and_account):
    client, account = client_and_account
    r = client.post(
        "/scans",
        headers={"X-Account-Id": account},
        json={"niche": "plumbers", "city": "austin", "limit": 4},
    )
    assert r.status_code == 402
    assert r.json()["detail"]["estimated_cost"] == 4


def test_confirmed_scan_succeeds_and_debits_balance(client_and_account):
    client, account = client_and_account
    r = client.post(
        "/scans",
        headers={"X-Account-Id": account},
        json={"niche": "plumbers", "city": "austin", "limit": 4, "confirmed": True},
    )
    assert r.status_code == 200
    assert r.json()["written"] == 4
    assert r.json()["spent"] == 4

    b = client.get("/balance", headers={"X-Account-Id": account})
    assert b.json()["balance"] == 46
