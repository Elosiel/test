"""Score aggregation — combines the three independent components into a rank.

Pure, deterministic. Rank is a weighted blend of opportunity/fit/confidence, each
already 0-100. Weights are NORMALIZED by their sum so rank stays within 0-100 even
if the configured weights don't sum to 1.0. Weights live in src/config.py.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.confidence import confidence_score
from src.domain.entities import Business, Persona
from src.domain.fit import fit_score
from src.domain.opportunity import opportunity_score


@dataclass(frozen=True)
class Weights:
    opportunity: float
    fit: float
    confidence: float


@dataclass(frozen=True)
class ScoreResult:
    opportunity: int
    fit: int
    confidence: int
    rank: float


def blend(opportunity: int, fit: int, confidence: int, weights: Weights) -> float:
    total = weights.opportunity + weights.fit + weights.confidence
    if total <= 0:
        raise ValueError("score weights must sum to a positive number")
    weighted = (
        opportunity * weights.opportunity
        + fit * weights.fit
        + confidence * weights.confidence
    )
    return round(weighted / total, 2)


def score_business(business: Business, persona: Persona, weights: Weights) -> ScoreResult:
    has_website = bool(business.website)
    opportunity = opportunity_score(
        business.rating, business.review_count,
        has_website=has_website, reviews=business.reviews,
    )
    fit = fit_score(business, persona)
    # At discovery time we hold no email yet; confidence reflects what we have now
    # and is recomputed once an email is found/verified (step 5).
    confidence = confidence_score(
        has_website=has_website,
        has_email=False,
        email_verified=False,
        rating=business.rating,
        review_count=business.review_count,
    )
    rank = blend(opportunity, fit, confidence, weights)
    return ScoreResult(opportunity=opportunity, fit=fit, confidence=confidence, rank=rank)
