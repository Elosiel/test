"""Shared delivery wiring: the injected ``Deps`` and a single ``execute_scan``
helper used by both the JSON API and the server-rendered web routes, so the scan
plumbing lives in exactly one place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from src.application.run_scan import RunScanResult, run_scan
from src.config import Config
from src.domain.entities import Persona, Territory
from src.domain.scoring import Weights
from src.ports.ai import AIPort
from src.ports.data_provider import DataProviderPort
from src.ports.email_finder import EmailFinderPort
from src.ports.email_sender import EmailSenderPort
from src.ports.payments import PaymentsPort
from src.ports.repositories import UnitOfWork


@dataclass
class Deps:
    """Everything the routes need, wired at the composition root."""
    config: Config
    data_provider: DataProviderPort
    ai: AIPort
    # account_id -> UnitOfWork factory, so each request's transactions are tenant-scoped.
    uow_factory_for: Callable[[str], Callable[[], UnitOfWork]]
    # Outreach ports (step 5). Optional so non-outreach wiring/tests can omit them.
    email_finder: EmailFinderPort | None = None
    email_sender: EmailSenderPort | None = None
    # Payments port (step 6). Optional like the outreach ports.
    payments: PaymentsPort | None = None


@dataclass
class ScanParams:
    niche: str
    city: str
    limit: int
    confirmed: bool = False
    target_category: str | None = None
    geo: str | None = None
    keywords: list[str] = field(default_factory=list)
    size_hint: str | None = None


def execute_scan(deps: Deps, account_id: str, params: ScanParams) -> RunScanResult:
    """Build the territory/persona/weights and run the scan. Raises the domain
    errors (ConfirmationRequired / InsufficientCredits / ValueError) for the caller
    to translate into an HTTP response.
    """
    territory = Territory(
        account_id=account_id, persona_id="", niche=params.niche, city=params.city
    )
    persona = Persona(
        account_id=account_id,
        name="inline",
        target_category=params.target_category or params.niche,
        geo=params.geo or params.city,
        keywords=params.keywords,
        size_hint=params.size_hint,
    )
    weights = Weights(
        opportunity=deps.config.weight_opportunity,
        fit=deps.config.weight_fit,
        confidence=deps.config.weight_confidence,
    )
    return run_scan(
        deps.uow_factory_for(account_id),
        deps.data_provider,
        account_id=account_id,
        territory=territory,
        persona=persona,
        weights=weights,
        limit=params.limit,
        credit_per_lead=deps.config.credit_per_lead,
        max_leads_per_run=deps.config.max_leads_per_run,
        confirmed=params.confirmed,
    )
