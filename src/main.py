"""Composition root: read config/secrets, wire adapters to ports, build the app.
This is the only module allowed to know about both adapters and delivery.
"""
from __future__ import annotations

from typing import Callable

from src.adapters.data.fake_data_provider import FakeDataProvider
from src.adapters.db.memory import MemoryStore, MemoryUnitOfWork
from src.application.accounts import ensure_tenant
from src.config import Config, load_config
from src.delivery.api.app import create_app
from src.delivery.deps import Deps
from src.ports.repositories import UnitOfWork


def _memory_uow_factory_for(store: MemoryStore) -> Callable[[str], Callable[[], UnitOfWork]]:
    # The in-memory store ignores account scoping at the factory level (the repos
    # filter by account_id); the same signature lets postgres scope per account.
    def for_account(_account_id: str) -> Callable[[], UnitOfWork]:
        return lambda: MemoryUnitOfWork(store)

    return for_account


def _postgres_uow_factory_for(dsn: str) -> Callable[[str], Callable[[], UnitOfWork]]:
    from src.adapters.db.postgres import PostgresUnitOfWork

    def for_account(account_id: str) -> Callable[[], UnitOfWork]:
        return lambda: PostgresUnitOfWork(dsn, account_id)

    return for_account


def build_deps(config: Config) -> Deps:
    data_provider = FakeDataProvider()  # real Outscraper adapter swaps in here later
    if config.backend == "postgres":
        assert config.database_url is not None  # guaranteed by Config.__post_init__
        uow_factory_for = _postgres_uow_factory_for(config.database_url)
    else:
        uow_factory_for = _memory_uow_factory_for(MemoryStore())
    return Deps(config=config, data_provider=data_provider, uow_factory_for=uow_factory_for)


def bootstrap_tenant(config: Config, deps: Deps) -> None:
    """Ensure the single tenant account exists with its free credits. Idempotent."""
    with deps.uow_factory_for(config.tenant_owner_user_id)() as uow:
        ensure_tenant(
            uow, config.tenant_owner_user_id, config.tenant_name, config.free_credits
        )
        uow.commit()


def build_app():
    config = load_config()
    deps = build_deps(config)
    if config.auth_mode == "session":
        bootstrap_tenant(config, deps)
    return create_app(deps)


# `uvicorn src.main:app` for local serving.
app = build_app()
