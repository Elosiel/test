"""RunScan — the vertical-slice use case that proves the spine.

DISCOVER businesses -> write N leads -> spend N credits, atomically.

Cost-safety / metering rules honored:
- confirm-before-spend: refuses to run until the caller confirms the estimate.
- a cheap pre-flight balance read avoids paying for a scan the account can't afford.
- the paid provider call happens OUTSIDE the write transaction (no network held
  open across the DB transaction).
- lead writes + the credit spend commit together; any failure rolls back both,
  so failed work is never billed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.application import credits
from src.domain.entities import Business, Lead, Run, Territory, new_id
from src.domain.errors import ConfirmationRequiredError, InsufficientCreditsError
from src.ports.data_provider import DataProviderPort
from src.ports.repositories import UnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]


@dataclass(frozen=True)
class RunScanResult:
    run_id: str
    found: int
    written: int
    spent: int


def estimate_scan_cost(limit: int, credit_per_lead: int) -> int:
    return limit * credit_per_lead


def _to_lead(business: Business, account_id: str, run_id: str) -> Lead:
    return Lead(
        account_id=account_id,
        run_id=run_id,
        name=business.name,
        category=business.category,
        address=business.address,
        phone=business.phone,
        website=business.website,
        rating=business.rating,
        review_count=business.review_count,
        source=business.source,
    )


def run_scan(
    uow_factory: UnitOfWorkFactory,
    data_provider: DataProviderPort,
    *,
    account_id: str,
    territory: Territory,
    limit: int,
    credit_per_lead: int,
    max_leads_per_run: int,
    confirmed: bool,
) -> RunScanResult:
    if limit <= 0:
        raise ValueError("limit must be positive")
    if limit > max_leads_per_run:
        raise ValueError(f"limit {limit} exceeds cap of {max_leads_per_run} leads/run")

    estimate = estimate_scan_cost(limit, credit_per_lead)
    if not confirmed:
        raise ConfirmationRequiredError(estimate)

    # Pre-flight: don't pay the provider for a scan the account can't afford.
    with uow_factory() as uow:
        available = credits.balance(uow, account_id)
    if available < estimate:
        raise InsufficientCreditsError(account_id, required=estimate, available=available)

    # Paid external call — outside the write transaction.
    businesses = data_provider.search(territory.niche, territory.city, limit)

    run_id = new_id()
    leads = [_to_lead(b, account_id, run_id) for b in businesses]
    cost = len(leads) * credit_per_lead

    # Persist results and spend credits in one transaction.
    with uow_factory() as uow:
        run = Run(  # id pinned to run_id so it matches the leads' run_id
            account_id=account_id,
            territory_id=territory.id,
            limit=limit,
            cost_credits=cost,
            summary={"found": len(businesses), "written": len(leads)},
            id=run_id,
        )
        uow.runs.add(run)
        for lead in leads:
            uow.leads.add(lead)
        if cost > 0:
            # Authoritative check happens inside spend(); rolls back on overdraft.
            credits.spend(uow, account_id, cost, reason=f"scan:{run_id}")
        uow.commit()

    return RunScanResult(run_id=run_id, found=len(businesses), written=len(leads), spent=cost)
