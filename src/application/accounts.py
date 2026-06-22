"""Account bootstrap. Pure application logic over ports — no IO of its own.

``ensure_tenant`` is idempotent: it creates the single tenant account if it does
not exist yet and grants the free-credit signup grant exactly once. Safe to call on
every startup.
"""
from __future__ import annotations

from src.application import credits
from src.domain.entities import Account
from src.ports.repositories import UnitOfWork

SIGNUP_GRANT_REASON = "signup:free"


def ensure_tenant(
    uow: UnitOfWork, owner_user_id: str, name: str, free_credits: int
) -> Account:
    """Create the tenant account + free-credit grant if missing. Caller commits."""
    account = uow.accounts.get_by_owner(owner_user_id)
    if account is None:
        account = Account(owner_user_id=owner_user_id, name=name)
        uow.accounts.add(account)
        if free_credits > 0:
            credits.grant(uow, account.id, free_credits, reason=SIGNUP_GRANT_REASON)
    return account
