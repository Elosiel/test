"""Payments — buy credit packs via the PaymentsPort, granted through the ledger.

The architecture's invariant: the webhook handler is **idempotent on event.id** and a
ledger row is written **only on success**. Idempotency is enforced twice — a pre-insert
check (``CreditRepo.event_exists``) and the DB ``UNIQUE(stripe_event_id)`` constraint — so
a replayed event can never double-grant.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.application import credits
from src.domain.entities import Pack
from src.domain.errors import LeadCenterError
from src.ports.payments import PaymentsPort, CheckoutSession
from src.ports.repositories import UnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


class PackNotFoundError(LeadCenterError):
    def __init__(self, pack_id: str) -> None:
        self.pack_id = pack_id
        super().__init__(f"pack {pack_id} not found or inactive")


# Default catalog, seeded idempotently at startup. Prices are placeholders until COGS
# is measured (an OPEN item in ARCHITECTURE.md) — do not treat as final.
DEFAULT_PACKS: list[dict] = [
    {"name": "Starter", "credits": 100, "price_cents": 2900},
    {"name": "Growth", "credits": 500, "price_cents": 9900},
    {"name": "Scale", "credits": 2000, "price_cents": 29900},
]


def ensure_packs(uow: UnitOfWork, catalog: list[dict] = DEFAULT_PACKS) -> None:
    """Seed the pack catalog if missing. Idempotent (keyed on pack name). Caller commits."""
    changed = False
    for spec in catalog:
        if uow.packs.get_by_name(spec["name"]) is None:
            uow.packs.add(Pack(**spec))
            changed = True
    if changed:
        uow.commit()


def list_active_packs(uow_factory: UnitOfWorkFactory) -> list[Pack]:
    with uow_factory() as uow:
        return uow.packs.list_active()


def start_checkout(
    uow_factory: UnitOfWorkFactory,
    payments: PaymentsPort,
    *,
    account_id: str,
    pack_id: str,
    success_url: str,
    cancel_url: str,
) -> CheckoutSession:
    with uow_factory() as uow:
        pack = uow.packs.get(pack_id)
    if pack is None or not pack.active:
        raise PackNotFoundError(pack_id)
    return payments.create_checkout(
        pack=pack, account_id=account_id, success_url=success_url, cancel_url=cancel_url
    )


def handle_webhook(
    uow_factory_for: Callable[[str], UnitOfWorkFactory],
    payments: PaymentsPort,
    payload: bytes,
    signature: str | None,
) -> bool:
    """Process a payment webhook. Returns True if credits were granted, False if the
    event was ignored or already processed (idempotent no-op). Raises on bad signature.

    The grant is scoped to the event's account (the factory is account-aware) so the
    ledger write satisfies Postgres RLS for that tenant.
    """
    event = payments.parse_event(payload, signature)
    if event is None:
        return False  # event type we don't handle

    with uow_factory_for(event.account_id)() as uow:
        if uow.credits.event_exists(event.id):
            return False  # already processed — idempotent no-op
        pack = uow.packs.get(event.pack_id)
        if pack is None:
            return False  # unknown pack — nothing to grant
        credits.grant(
            uow, event.account_id, pack.credits,
            reason=f"purchase:{pack.name}", stripe_event_id=event.id,
        )
        uow.commit()
    return True
