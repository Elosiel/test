"""Pitch generation — on-demand per lead (AI only at the edges, cost-safe).

Drafting one pitch loads the lead, asks the AIPort for a <=150-word first email
(signal-first when the lead is hot, else gap-first), stores it on the lead, and
spends one credit — all in a single transaction, so a failed generation is never
billed and never leaves a half-written lead.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Callable

from src.application import credits
from src.domain.entities import Lead
from src.domain.errors import LeadNotFoundError
from src.ports.ai import AIPort, PitchBrief
from src.ports.repositories import UnitOfWork

UnitOfWorkFactory = Callable[[], UnitOfWork]

__all__ = ["LeadNotFoundError", "build_brief", "draft_pitch"]


def build_brief(lead: Lead) -> PitchBrief:
    return PitchBrief(
        business_name=lead.name,
        category=lead.category,
        mode="signal" if lead.hot_signal else "gap",
        hot_signal=lead.hot_signal,
        fresh_pain=lead.fresh_pain,
        primary_gap=lead.primary_gap,
        rating=lead.rating,
        review_count=lead.review_count,
    )


def draft_pitch(
    uow_factory: UnitOfWorkFactory,
    ai: AIPort,
    *,
    account_id: str,
    lead_id: str,
    credit_per_pitch: int,
) -> Lead:
    with uow_factory() as uow:
        lead = uow.leads.get(account_id, lead_id)
        if lead is None:
            raise LeadNotFoundError(lead_id)

        # Generate before spending; if the model raises, we never billed.
        pitch = ai.generate_pitch(build_brief(lead))

        updated = replace(lead, pitch=pitch)
        uow.leads.update(updated)
        if credit_per_pitch > 0:
            credits.spend(uow, account_id, credit_per_pitch, reason=f"pitch:{lead_id}")
        uow.commit()
    return updated
