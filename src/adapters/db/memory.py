"""In-memory UnitOfWork. Backs local runs and the application/unit tests with no
database. Models real transaction semantics: writes are staged and only applied to
the shared store on ``commit``; leaving the ``with`` block uncommitted discards
them (rollback).

Account scoping here mirrors what RLS enforces at the DB — repos only ever return
rows for the requested ``account_id``. The hard guarantee is still the database's
job and is covered by tests/integration/test_rls.py against real Postgres.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.entities import Account, CreditLedgerEntry, Lead, Run


@dataclass
class MemoryStore:
    """The shared 'database'. One instance is shared across UnitOfWork sessions."""
    accounts: list[Account] = field(default_factory=list)
    leads: list[Lead] = field(default_factory=list)
    runs: list[Run] = field(default_factory=list)
    ledger: list[CreditLedgerEntry] = field(default_factory=list)


class _AccountRepo:
    def __init__(self, store: MemoryStore, staged: list[Account]) -> None:
        self._store = store
        self._staged = staged

    def add(self, account: Account) -> None:
        self._staged.append(account)

    def get(self, account_id: str) -> Account | None:
        return next(
            (a for a in (*self._store.accounts, *self._staged) if a.id == account_id), None
        )

    def get_by_owner(self, owner_user_id: str) -> Account | None:
        return next(
            (a for a in (*self._store.accounts, *self._staged)
             if a.owner_user_id == owner_user_id),
            None,
        )


class _LeadRepo:
    def __init__(self, store: MemoryStore, staged: list[Lead]) -> None:
        self._store = store
        self._staged = staged

    def add(self, lead: Lead) -> None:
        self._staged.append(lead)

    def list_for_account(self, account_id: str) -> list[Lead]:
        return [l for l in (*self._store.leads, *self._staged) if l.account_id == account_id]


class _RunRepo:
    def __init__(self, staged: list[Run]) -> None:
        self._staged = staged

    def add(self, run: Run) -> None:
        self._staged.append(run)


class _CreditRepo:
    def __init__(self, store: MemoryStore, staged: list[CreditLedgerEntry]) -> None:
        self._store = store
        self._staged = staged

    def record(self, entry: CreditLedgerEntry) -> None:
        self._staged.append(entry)

    def balance(self, account_id: str) -> int:
        return sum(
            e.delta
            for e in (*self._store.ledger, *self._staged)
            if e.account_id == account_id
        )


class MemoryUnitOfWork:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def __enter__(self) -> "MemoryUnitOfWork":
        self._staged_accounts: list[Account] = []
        self._staged_leads: list[Lead] = []
        self._staged_runs: list[Run] = []
        self._staged_ledger: list[CreditLedgerEntry] = []
        self.accounts = _AccountRepo(self._store, self._staged_accounts)
        self.leads = _LeadRepo(self._store, self._staged_leads)
        self.runs = _RunRepo(self._staged_runs)
        self.credits = _CreditRepo(self._store, self._staged_ledger)
        self._committed = False
        return self

    def commit(self) -> None:
        self._store.accounts.extend(self._staged_accounts)
        self._store.leads.extend(self._staged_leads)
        self._store.runs.extend(self._staged_runs)
        self._store.ledger.extend(self._staged_ledger)
        self._committed = True

    def rollback(self) -> None:
        self._staged_accounts.clear()
        self._staged_leads.clear()
        self._staged_runs.clear()
        self._staged_ledger.clear()

    def __exit__(self, exc_type, exc, tb) -> bool:
        if not self._committed:
            self.rollback()
        return False  # never suppress exceptions
