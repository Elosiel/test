"""draft_pitch: transactional metering, signal-first vs gap-first, rollback."""
from __future__ import annotations

import pytest

from src.adapters.ai.fake_ai_adapter import FakeAI
from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.application import credits
from src.application.pitch import LeadNotFoundError, draft_pitch
from src.domain.entities import Lead, new_id
from src.domain.errors import InsufficientCreditsError


def _factory(store):
    return lambda: MemoryUnitOfWork(store)


def _seed(store, account_id, balance, **lead_kwargs):
    with _factory(store)() as uow:
        if balance:
            credits.grant(uow, account_id, balance, reason="seed")
        lead = Lead(account_id=account_id, run_id="r", name="Acme", **lead_kwargs)
        uow.leads.add(lead)
        uow.commit()
    return lead


def test_draft_spends_one_credit_and_stores_pitch():
    store, acct = MemoryStore(), new_id()
    lead = _seed(store, acct, 10, primary_gap="no website")

    updated = draft_pitch(
        _factory(store), FakeAI(), account_id=acct, lead_id=lead.id, credit_per_pitch=1
    )

    assert updated.pitch
    with _factory(store)() as uow:
        assert credits.balance(uow, acct) == 9
        assert uow.leads.get(acct, lead.id).pitch == updated.pitch


def test_signal_first_when_hot_else_gap_first():
    store, acct = MemoryStore(), new_id()
    hot = _seed(store, acct, 10, hot_signal=True,
                fresh_pain={"review_age_days": 3, "rating": 2.0, "unanswered": True})
    cold = _seed(store, acct, 10, hot_signal=False, primary_gap="no website")

    hot_pitch = draft_pitch(_factory(store), FakeAI(), account_id=acct,
                            lead_id=hot.id, credit_per_pitch=1).pitch
    cold_pitch = draft_pitch(_factory(store), FakeAI(), account_id=acct,
                             lead_id=cold.id, credit_per_pitch=1).pitch

    assert "review" in hot_pitch.lower()
    assert "no website" in cold_pitch.lower()
    assert len(hot_pitch.split()) <= 150
    assert len(cold_pitch.split()) <= 150


def test_insufficient_credits_rejects_and_stores_nothing():
    store, acct = MemoryStore(), new_id()
    lead = _seed(store, acct, 0, primary_gap="no website")  # zero balance

    with pytest.raises(InsufficientCreditsError):
        draft_pitch(_factory(store), FakeAI(), account_id=acct, lead_id=lead.id,
                    credit_per_pitch=1)

    with _factory(store)() as uow:
        assert uow.leads.get(acct, lead.id).pitch is None  # rolled back
        assert credits.balance(uow, acct) == 0


def test_unknown_lead_raises():
    store, acct = MemoryStore(), new_id()
    with _factory(store)() as uow:
        credits.grant(uow, acct, 10, reason="seed")
        uow.commit()
    with pytest.raises(LeadNotFoundError):
        draft_pitch(_factory(store), FakeAI(), account_id=acct, lead_id="nope",
                    credit_per_pitch=1)
