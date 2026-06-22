"""FastAPI surface for the spine. DTOs + routes only; all wiring is injected by the
composition root (src/main.py) so this module imports no adapters.

Auth note: the v1 spine derives the tenant from an ``X-Account-Id`` header. This is
a placeholder for Supabase Auth/JWT (build-order: real auth lands with outreach).
It is clearly a stand-in, not production auth.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.application import credits
from src.application.run_scan import RunScanResult
from src.delivery.auth import make_current_account
from src.delivery.deps import Deps, ScanParams, execute_scan
from src.domain.errors import ConfirmationRequiredError, InsufficientCreditsError


class ScanRequest(BaseModel):
    niche: str = Field(min_length=1)
    city: str = Field(min_length=1)
    limit: int = Field(gt=0)
    confirmed: bool = False
    # Inline persona for Fit scoring (no persona storage yet). All optional;
    # absent fields are neutralized by the Fit scorer.
    target_category: str | None = None
    geo: str | None = None
    keywords: list[str] = Field(default_factory=list)
    size_hint: str | None = None


class ScanResponse(BaseModel):
    run_id: str
    found: int
    written: int
    spent: int


class LeadDTO(BaseModel):
    id: str
    name: str
    category: str | None
    rating: float | None
    review_count: int | None
    opportunity: int
    fit: int
    confidence: int
    rank: float
    status: str


class BalanceResponse(BaseModel):
    account_id: str
    balance: int


def create_app(deps: Deps) -> FastAPI:
    from src.delivery.web.routes import create_web_router

    app = FastAPI(title="Lead///Center", version="0.1.0")
    require_account = make_current_account(deps.config)
    app.include_router(create_web_router(deps))

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/balance", response_model=BalanceResponse)
    def get_balance(account_id: str = Depends(require_account)) -> BalanceResponse:
        uow_factory = deps.uow_factory_for(account_id)
        with uow_factory() as uow:
            return BalanceResponse(account_id=account_id, balance=credits.balance(uow, account_id))

    @app.post("/scans", response_model=ScanResponse)
    def post_scan(
        body: ScanRequest, account_id: str = Depends(require_account)
    ) -> ScanResponse:
        params = ScanParams(
            niche=body.niche, city=body.city, limit=body.limit, confirmed=body.confirmed,
            target_category=body.target_category, geo=body.geo,
            keywords=body.keywords, size_hint=body.size_hint,
        )
        try:
            result: RunScanResult = execute_scan(deps, account_id, params)
        except ConfirmationRequiredError as e:
            # 402 Payment Required: surface the estimate so the client can confirm.
            raise HTTPException(
                status_code=402,
                detail={"error": "confirmation_required", "estimated_cost": e.estimated_cost},
            )
        except InsufficientCreditsError as e:
            raise HTTPException(
                status_code=402,
                detail={"error": "insufficient_credits", "required": e.required, "available": e.available},
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        return ScanResponse(**result.__dict__)

    @app.get("/leads", response_model=list[LeadDTO])
    def list_leads(account_id: str = Depends(require_account)) -> list[LeadDTO]:
        """Radar feed: the account's leads, highest rank first."""
        uow_factory = deps.uow_factory_for(account_id)
        with uow_factory() as uow:
            leads = uow.leads.list_for_account(account_id)
        leads.sort(key=lambda l: l.rank, reverse=True)
        return [
            LeadDTO(
                id=l.id,
                name=l.name,
                category=l.category,
                rating=l.rating,
                review_count=l.review_count,
                opportunity=l.opportunity,
                fit=l.fit,
                confidence=l.confidence,
                rank=l.rank,
                status=l.status.value,
            )
            for l in leads
        ]

    return app
