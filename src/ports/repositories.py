"""Repository and unit-of-work ports.

The UnitOfWork is the transaction boundary. The architecture's core invariant —
"a credit is spent inside the same transaction that writes the result" — is
expressed by acquiring repos from a single UnitOfWork and calling ``commit`` once.
On any exception, leaving the ``with`` block rolls everything back.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.entities import Account, CreditLedgerEntry, Lead, Run


class AccountRepo(Protocol):
    def add(self, account: Account) -> None: ...
    def get(self, account_id: str) -> Account | None: ...
    def get_by_owner(self, owner_user_id: str) -> Account | None: ...


class LeadRepo(Protocol):
    def add(self, lead: Lead) -> None: ...
    def list_for_account(self, account_id: str) -> list[Lead]: ...
    def get(self, account_id: str, lead_id: str) -> Lead | None: ...
    def update(self, lead: Lead) -> None: ...


class RunRepo(Protocol):
    def add(self, run: Run) -> None: ...


class CreditRepo(Protocol):
    def record(self, entry: CreditLedgerEntry) -> None: ...
    def balance(self, account_id: str) -> int:
        """Derived balance: SUM(delta) for the account. Never a stored counter."""
        ...


@runtime_checkable
class UnitOfWork(Protocol):
    accounts: AccountRepo
    leads: LeadRepo
    runs: RunRepo
    credits: CreditRepo

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type, exc, tb) -> bool | None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
