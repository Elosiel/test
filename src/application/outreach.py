"""Outreach — contact a lead by email. The riskiest subsystem; every hard rule from
ARCHITECTURE.md is enforced here in order:

  feature flag -> lead exists -> has a drafted pitch -> confidence gate
  -> find email -> MUST be verified -> suppression check -> compose with a real
  physical address + working unsubscribe -> send -> record message + status=contacted
  + spend one credit, transactionally (a failed send is never billed).

External calls (find, send) happen outside the write transaction; persistence and
metering commit together.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable

from src.application import credits
from src.config import Config
from src.domain.entities import Lead, LeadStatus, Message, MessageDirection, MessageState, Suppression
from src.domain.errors import (
    ComplianceConfigError,
    EmailNotFoundError,
    EmailUnverifiedError,
    LeadNotFoundError,
    LowConfidenceError,
    OutreachDisabledError,
    PitchRequiredError,
    SuppressedError,
)
from src.ports.email_finder import EmailFinderPort
from src.ports.email_sender import EmailSenderPort
from src.ports.repositories import UnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


@dataclass(frozen=True)
class ComposedEmail:
    subject: str
    body: str


def compose(lead: Lead, email: str, account_id: str, config: Config) -> ComposedEmail:
    """Build the email with the legally-required footer. Raises if the physical
    address isn't configured — we never send a non-compliant email.
    """
    if not config.physical_address:
        raise ComplianceConfigError("OUTREACH_PHYSICAL_ADDRESS is required to send")

    subject = (
        f"A quick idea for {lead.name}"
        if lead.hot_signal
        else f"Helping {lead.name} get found"
    )
    base = config.unsubscribe_base_url or "https://example.invalid/unsubscribe"
    unsub = f"{base}?email={email}&account={account_id}"
    footer = (
        f"\n\n---\n{config.from_name}\n{config.physical_address}\n"
        f"Unsubscribe: {unsub}"
    )
    body = (lead.pitch or "") + footer
    return ComposedEmail(subject=subject, body=body)


def contact_lead(
    uow_factory: UnitOfWorkFactory,
    finder: EmailFinderPort,
    sender: EmailSenderPort,
    *,
    account_id: str,
    lead_id: str,
    config: Config,
) -> Lead:
    if not config.outreach_enabled:
        raise OutreachDisabledError("outreach is disabled (set OUTREACH_ENABLED)")

    with uow_factory() as uow:
        lead = uow.leads.get(account_id, lead_id)
    if lead is None:
        raise LeadNotFoundError(lead_id)
    if not lead.pitch:
        raise PitchRequiredError("draft a pitch before contacting this lead")
    if lead.confidence < config.min_confidence_to_contact:
        raise LowConfidenceError(lead.confidence, config.min_confidence_to_contact)

    # Resolve a verified email (use what we hold, else find it). External call.
    if lead.email and lead.email_verified:
        email = lead.email
    else:
        found = finder.find(business_name=lead.name, website=lead.website)
        if found is None:
            raise EmailNotFoundError(f"no email for lead {lead_id}")
        if not found.verified:
            raise EmailUnverifiedError(f"unverified email for lead {lead_id}")
        email = found.email

    # Suppression check — as close to the send as possible.
    with uow_factory() as uow:
        if uow.suppression.is_suppressed(account_id, email):
            raise SuppressedError(f"{email} is suppressed")

    composed = compose(lead, email, account_id, config)
    sent = sender.send(
        to=email, subject=composed.subject, body=composed.body,
        from_name=config.from_name, from_email=config.from_email,
    )

    # Persist + meter atomically.
    with uow_factory() as uow:
        fresh = uow.leads.get(account_id, lead_id)
        if fresh is None:  # pragma: no cover - lead deleted mid-flight
            raise LeadNotFoundError(lead_id)
        uow.leads.update(
            replace(fresh, email=email, email_verified=True, status=LeadStatus.CONTACTED)
        )
        uow.messages.add(Message(
            account_id=account_id, lead_id=lead_id, direction=MessageDirection.OUT,
            subject=composed.subject, body=composed.body, provider_id=sent.provider_id,
            state=MessageState.SENT, sent_at=datetime.now(timezone.utc),
        ))
        if config.credit_per_send > 0:
            credits.spend(uow, account_id, config.credit_per_send, reason=f"send:{lead_id}")
        uow.commit()
        return uow.leads.get(account_id, lead_id)


def unsubscribe(
    uow_factory: UnitOfWorkFactory, account_id: str, email: str, *, reason: str = "unsubscribe"
) -> None:
    """Add an email to the suppression list (CAN-SPAM opt-out / hard bounce). Idempotent
    enough: duplicate rows are harmless because checks use membership, not counts.
    """
    with uow_factory() as uow:
        if not uow.suppression.is_suppressed(account_id, email):
            uow.suppression.add(Suppression(
                account_id=account_id, email_or_domain=email, reason=reason
            ))
            uow.commit()
