"""Outreach hard rules — each compliance/safety gate gets an explicit test."""
from __future__ import annotations

import pytest

from src.adapters.email.fake_finder import FakeEmailFinder
from src.adapters.email.fake_sender import FakeEmailSender
from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.application import credits
from src.application.outreach import contact_lead, unsubscribe
from src.config import Config
from src.domain.entities import Lead, LeadStatus, Suppression, new_id
from src.domain.errors import (
    ComplianceConfigError,
    EmailNotFoundError,
    InsufficientCreditsError,
    LowConfidenceError,
    OutreachDisabledError,
    PitchRequiredError,
    SuppressedError,
)


def _config(**overrides) -> Config:
    base = dict(
        backend="memory",
        outreach_enabled=True,
        physical_address="123 Main St, Austin TX 78701",
        from_email="hi@fluxo.test",
        unsubscribe_base_url="https://fluxo.test/unsub",
    )
    base.update(overrides)
    return Config(**base)


def _factory(store):
    return lambda: MemoryUnitOfWork(store)


def _seed_lead(store, account_id, *, balance=5, **lead_kwargs):
    defaults = dict(
        name="Acme", website="https://acme.test", confidence=70,
        pitch="Hi there, quick idea.", status=LeadStatus.NEW,
    )
    defaults.update(lead_kwargs)
    with _factory(store)() as uow:
        if balance:
            credits.grant(uow, account_id, balance, reason="seed")
        lead = Lead(account_id=account_id, run_id="r", **defaults)
        uow.leads.add(lead)
        uow.commit()
    return lead


def test_happy_path_sends_records_and_debits():
    store, acct, finder, sender = MemoryStore(), new_id(), FakeEmailFinder(), FakeEmailSender()
    lead = _seed_lead(store, acct)

    updated = contact_lead(_factory(store), finder, sender,
                           account_id=acct, lead_id=lead.id, config=_config())

    assert updated.status == LeadStatus.CONTACTED
    assert updated.email == "info@acme.test"
    assert updated.email_verified is True
    assert len(sender.sent) == 1
    with _factory(store)() as uow:
        assert credits.balance(uow, acct) == 4
    assert len(store.messages) == 1
    # CAN-SPAM: body carries the physical address and an unsubscribe link.
    body = store.messages[0].body
    assert "123 Main St" in body
    assert "Unsubscribe:" in body


def test_disabled_blocks():
    store, acct = MemoryStore(), new_id()
    lead = _seed_lead(store, acct)
    with pytest.raises(OutreachDisabledError):
        contact_lead(_factory(store), FakeEmailFinder(), FakeEmailSender(),
                     account_id=acct, lead_id=lead.id, config=_config(outreach_enabled=False))


def test_missing_pitch_blocks():
    store, acct = MemoryStore(), new_id()
    lead = _seed_lead(store, acct, pitch=None)
    with pytest.raises(PitchRequiredError):
        contact_lead(_factory(store), FakeEmailFinder(), FakeEmailSender(),
                     account_id=acct, lead_id=lead.id, config=_config())


def test_low_confidence_blocks():
    store, acct = MemoryStore(), new_id()
    lead = _seed_lead(store, acct, confidence=10)
    with pytest.raises(LowConfidenceError):
        contact_lead(_factory(store), FakeEmailFinder(), FakeEmailSender(),
                     account_id=acct, lead_id=lead.id, config=_config())


def test_no_email_blocks():
    store, acct = MemoryStore(), new_id()
    lead = _seed_lead(store, acct, website=None)  # finder can't derive an email
    with pytest.raises(EmailNotFoundError):
        contact_lead(_factory(store), FakeEmailFinder(), FakeEmailSender(),
                     account_id=acct, lead_id=lead.id, config=_config())


def test_suppressed_recipient_blocks():
    store, acct = MemoryStore(), new_id()
    lead = _seed_lead(store, acct)
    with _factory(store)() as uow:
        uow.suppression.add(Suppression(account_id=acct, email_or_domain="info@acme.test",
                                        reason="unsubscribe"))
        uow.commit()
    with pytest.raises(SuppressedError):
        contact_lead(_factory(store), FakeEmailFinder(), FakeEmailSender(),
                     account_id=acct, lead_id=lead.id, config=_config())


def test_missing_physical_address_blocks_send():
    store, acct, sender = MemoryStore(), new_id(), FakeEmailSender()
    lead = _seed_lead(store, acct)
    with pytest.raises(ComplianceConfigError):
        contact_lead(_factory(store), FakeEmailFinder(), sender,
                     account_id=acct, lead_id=lead.id, config=_config(physical_address=""))
    assert sender.sent == []  # nothing left the building


def test_insufficient_credits_rolls_back():
    store, acct = MemoryStore(), new_id()
    lead = _seed_lead(store, acct, balance=0)
    with pytest.raises(InsufficientCreditsError):
        contact_lead(_factory(store), FakeEmailFinder(), FakeEmailSender(),
                     account_id=acct, lead_id=lead.id, config=_config())
    with _factory(store)() as uow:
        fresh = uow.leads.get(acct, lead.id)
    assert fresh.status == LeadStatus.NEW  # not marked contacted
    assert store.messages == []


def test_unsubscribe_then_contact_blocked():
    store, acct = MemoryStore(), new_id()
    lead = _seed_lead(store, acct)
    unsubscribe(_factory(store), acct, "info@acme.test")
    with _factory(store)() as uow:
        assert uow.suppression.is_suppressed(acct, "info@acme.test")
    with pytest.raises(SuppressedError):
        contact_lead(_factory(store), FakeEmailFinder(), FakeEmailSender(),
                     account_id=acct, lead_id=lead.id, config=_config())
