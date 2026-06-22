"""Server-rendered Radar feed flow in session-auth mode: login gate, login,
dashboard render, scan-via-form (debits balance), logout.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.ai.fake_ai_adapter import FakeAI
from src.adapters.data.fake_data_provider import FakeDataProvider
from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.application.accounts import ensure_tenant
from src.config import Config
from src.delivery.api.app import create_app
from src.delivery.deps import Deps

PASSWORD = "s3cret-pw"


@pytest.fixture
def client():
    store = MemoryStore()
    config = Config(
        backend="memory",
        auth_mode="session",
        session_secret="unit-test-secret-key-not-default",
        login_password=PASSWORD,
    )
    deps = Deps(
        config=config,
        data_provider=FakeDataProvider(),
        ai=FakeAI(),
        uow_factory_for=lambda _acct: (lambda: MemoryUnitOfWork(store)),
    )
    with MemoryUnitOfWork(store) as uow:
        ensure_tenant(uow, config.tenant_owner_user_id, config.tenant_name, config.free_credits)
        uow.commit()
    return TestClient(create_app(deps))


def _login(client) -> None:
    r = client.post("/login", data={"password": PASSWORD}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_dashboard_requires_login(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_wrong_password_rejected(client):
    r = client.post("/login", data={"password": "nope"}, follow_redirects=False)
    assert r.status_code == 401
    assert "Wrong password" in r.text
    # No session cookie issued -> still gated.
    assert client.get("/", follow_redirects=False).status_code == 303


def test_login_then_dashboard_renders(client):
    _login(client)
    r = client.get("/")
    assert r.status_code == 200
    assert "Radar" in r.text
    assert "credits" in r.text


def test_scan_via_form_debits_balance_and_lists_leads(client):
    _login(client)
    r = client.post(
        "/scan",
        data={"niche": "plumbers", "city": "austin", "limit": "5", "confirmed": "1"},
        follow_redirects=False,
    )
    assert r.status_code == 303  # PRG

    dash = client.get("/").text
    assert "fake data" in dash  # honesty badge on placeholder leads
    # 50 free credits - 5 = 45 remaining.
    assert "45 credits" in dash


def test_unconfirmed_scan_shows_estimate_error(client):
    _login(client)
    r = client.post(
        "/scan",
        data={"niche": "plumbers", "city": "austin", "limit": "5"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "confirm spend" in r.text or "credits" in r.text


def test_hot_badge_and_draft_flow(client):
    _login(client)
    client.post(
        "/scan",
        data={"niche": "plumbers", "city": "austin", "limit": "3", "confirmed": "1"},
        follow_redirects=False,
    )
    dash = client.get("/").text
    assert "🔥" in dash  # at least one hot lead from the fake provider
    assert ">Draft<" in dash  # draft buttons present

    # Grab a lead id from the JSON API (same store) and draft via the web route.
    import re
    m = re.search(r"/leads/([0-9a-f-]+)/draft", dash)
    assert m
    r = client.post(f"/leads/{m.group(1)}/draft", follow_redirects=False)
    assert r.status_code == 303
    assert "pitch" in client.get("/").text.lower()


def test_logout_clears_session(client):
    _login(client)
    assert client.get("/", follow_redirects=False).status_code == 200
    client.get("/logout", follow_redirects=False)
    assert client.get("/", follow_redirects=False).status_code == 303
