"""Shared fixtures and fakes for the test suite."""
from __future__ import annotations

from typing import Callable

import pytest

from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.application import credits
from src.domain.entities import new_id
from src.ports.repositories import UnitOfWork

UoWFactory = Callable[[], UnitOfWork]


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def uow_factory(store: MemoryStore) -> UoWFactory:
    return lambda: MemoryUnitOfWork(store)


@pytest.fixture
def account_id() -> str:
    return new_id()


@pytest.fixture
def grant_credits(uow_factory: UoWFactory) -> Callable[[str, int], None]:
    """Helper to seed an account's balance via a committed ledger grant."""

    def _grant(account: str, amount: int) -> None:
        with uow_factory() as uow:
            credits.grant(uow, account, amount, reason="test:seed")
            uow.commit()

    return _grant
