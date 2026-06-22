"""Credit metering — the financial source of truth.

Invariants enforced here:
- Balance is derived (SUM of ledger deltas), never a mutable counter.
- A spend is rejected if it would drive the balance negative.
- ``spend`` / ``grant`` only stage a ledger row on the given UnitOfWork; the
  caller commits so the spend lands in the same transaction as the result it pays
  for. Never bill failed work.
"""
from __future__ import annotations

from src.domain.entities import CreditLedgerEntry
from src.domain.errors import InsufficientCreditsError
from src.ports.repositories import UnitOfWork


def balance(uow: UnitOfWork, account_id: str) -> int:
    return uow.credits.balance(account_id)


def grant(
    uow: UnitOfWork,
    account_id: str,
    amount: int,
    reason: str,
    *,
    stripe_event_id: str | None = None,
) -> CreditLedgerEntry:
    """Stage a positive ledger entry. Caller must commit the UnitOfWork."""
    if amount <= 0:
        raise ValueError("grant amount must be positive")
    current = uow.credits.balance(account_id)
    entry = CreditLedgerEntry(
        account_id=account_id,
        delta=amount,
        reason=reason,
        balance_after=current + amount,
        stripe_event_id=stripe_event_id,
    )
    uow.credits.record(entry)
    return entry


def spend(uow: UnitOfWork, account_id: str, amount: int, reason: str) -> CreditLedgerEntry:
    """Stage a negative ledger entry, rejecting an overdraft. Caller must commit."""
    if amount <= 0:
        raise ValueError("spend amount must be positive")
    current = uow.credits.balance(account_id)
    if current < amount:
        raise InsufficientCreditsError(account_id, required=amount, available=current)
    entry = CreditLedgerEntry(
        account_id=account_id,
        delta=-amount,
        reason=reason,
        balance_after=current - amount,
    )
    uow.credits.record(entry)
    return entry
