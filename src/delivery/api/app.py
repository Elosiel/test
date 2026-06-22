"""FastAPI surface for the spine. DTOs + routes only; all wiring is injected by the
composition root (src/main.py) so this module imports no adapters.

Auth note: the v1 spine derives the tenant from an ``X-Account-Id`` header. This is
a placeholder for Supabase Auth/JWT (build-order: real auth lands with outreach).
It is clearly a stand-in, not production auth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from src.application import credits
from src.application.run_scan import RunScanResult, run_scan
from src.config import Config
from src.domain.entities import Territory
from src.domain.errors import ConfirmationRequiredError, InsufficientCreditsError
from src.ports.data_provider import DataProviderPort
from src.ports.repositories import UnitOfWork


@dataclass
class Deps:
    """Everything the routes need, wired at the composition root."""
    config: Config
    data_provider: DataProviderPort
    # account_id -> UnitOfWork, so each request's transactions are tenant-scoped.
    uow_factory_for: Callable[[str], Callable[[], UnitOfWork]]


class ScanRequest(BaseModel):
    niche: str = Field(min_length=1)
    city: str = Field(min_length=1)
    limit: int = Field(gt=0)
    confirmed: bool = False


class ScanResponse(BaseModel):
    run_id: str
    found: int
    written: int
    spent: int


class BalanceResponse(BaseModel):
    account_id: str
    balance: int


def require_account(x_account_id: str | None = Header(default=None)) -> str:
    if not x_account_id:
        raise HTTPException(status_code=401, detail="missing X-Account-Id header")
    return x_account_id


def create_app(deps: Deps) -> FastAPI:
    app = FastAPI(title="Lead///Center", version="0.1.0")

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
        territory = Territory(
            account_id=account_id, persona_id="", niche=body.niche, city=body.city
        )
        try:
            result: RunScanResult = run_scan(
                deps.uow_factory_for(account_id),
                deps.data_provider,
                account_id=account_id,
                territory=territory,
                limit=body.limit,
                credit_per_lead=deps.config.credit_per_lead,
                max_leads_per_run=deps.config.max_leads_per_run,
                confirmed=body.confirmed,
            )
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

    return app
