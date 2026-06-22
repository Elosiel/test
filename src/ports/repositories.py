"""Repository and unit-of-work ports.

The UnitOfWork is the transaction boundary. The architecture's core invariant —
"a credit is spent inside the same transaction that writes the result" — is
expressed by acquiring repos from a single UnitOfWork and calling ``commit`` once.
On any exception, leaving the ``with`` block rolls everything back.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities import CreditLedgerEntry, Lead, Run


class LeadRepo(Protocol):
    def add(self, lead: Lead) -> None: ...
    def list_for_account(self, account_id: str) -> list[Lead]: ...


class RunRepo(Protocol):
    def add(self, run: Run) -> None: ...


class CreditRepo(Protocol):
    def record(self, entry: CreditLedgerEntry) -> None: ...
    def balance(self, account_id: str) -> int:
        """Derived balance: SUM(delta) for the account. Never a stored counter."""
        ...


@runtime_checkable
class UnitOfWork(Protocol):
    leads: LeadRepo
    runs: RunRepo
    credits: CreditRepo

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> bool | None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
