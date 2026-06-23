"""FastAPI surface for the spine. DTOs + routes only; all wiring is injected by the
composition root (src/main.py) so this module imports no adapters.

Auth note: the v1 spine derives the tenant from an ``X-Account-Id`` header. This is
a placeholder for Supabase Auth/JWT (build-order: real auth lands with outreach).
It is clearly a stand-in, not production auth.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from src.application import credits
from src.application.outreach import contact_lead, unsubscribe
from src.application.payments import PackNotFoundError, handle_webhook, list_active_packs, start_checkout
from src.application.pitch import draft_pitch
from src.application.run_scan import RunScanResult
from src.delivery.auth import make_current_account
from src.delivery.deps import Deps, ScanParams, execute_scan
from src.domain.entities import Lead
from src.domain.errors import (
    ComplianceConfigError,
    ConfirmationRequiredError,
    EmailNotFoundError,
    EmailUnverifiedError,
    InsufficientCreditsError,
    LeadNotFoundError,
    LowConfidenceError,
    OutreachDisabledError,
    PitchRequiredError,
    SuppressedError,
)


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
    hot_signal: bool
    primary_gap: str | None
    pitch: str | None

    @classmethod
    def from_lead(cls, l: Lead) -> "LeadDTO":
        return cls(
            id=l.id, name=l.name, category=l.category, rating=l.rating,
            review_count=l.review_count, opportunity=l.opportunity, fit=l.fit,
            confidence=l.confidence, rank=l.rank, status=l.status.value,
            hot_signal=l.hot_signal, primary_gap=l.primary_gap, pitch=l.pitch,
        )


class BalanceResponse(BaseModel):
    account_id: str
    balance: int


class PackDTO(BaseModel):
    id: str
    name: str
    credits: int
    price_cents: int


class CheckoutRequest(BaseModel):
    pack_id: str


class CheckoutResponse(BaseModel):
    checkout_url: str


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
        return [LeadDTO.from_lead(l) for l in leads]

    @app.post("/leads/{lead_id}/pitch", response_model=LeadDTO)
    def post_pitch(lead_id: str, account_id: str = Depends(require_account)) -> LeadDTO:
        try:
            lead = draft_pitch(
                deps.uow_factory_for(account_id),
                deps.ai,
                account_id=account_id,
                lead_id=lead_id,
                credit_per_pitch=deps.config.credit_per_pitch,
            )
        except LeadNotFoundError:
            raise HTTPException(status_code=404, detail="lead not found")
        except InsufficientCreditsError as e:
            raise HTTPException(
                status_code=402,
                detail={"error": "insufficient_credits", "required": e.required,
                        "available": e.available},
            )
        return LeadDTO.from_lead(lead)

    @app.post("/leads/{lead_id}/contact", response_model=LeadDTO)
    def post_contact(lead_id: str, account_id: str = Depends(require_account)) -> LeadDTO:
        try:
            lead = contact_lead(
                deps.uow_factory_for(account_id),
                deps.email_finder,
                deps.email_sender,
                account_id=account_id,
                lead_id=lead_id,
                config=deps.config,
            )
        except OutreachDisabledError:
            raise HTTPException(status_code=403, detail="outreach is disabled")
        except LeadNotFoundError:
            raise HTTPException(status_code=404, detail="lead not found")
        except InsufficientCreditsError as e:
            raise HTTPException(
                status_code=402,
                detail={"error": "insufficient_credits", "required": e.required,
                        "available": e.available},
            )
        except (PitchRequiredError, LowConfidenceError, EmailNotFoundError,
                EmailUnverifiedError, SuppressedError, ComplianceConfigError) as e:
            raise HTTPException(status_code=409, detail={"error": type(e).__name__,
                                                         "message": str(e)})
        return LeadDTO.from_lead(lead)

    @app.get("/unsubscribe", response_class=PlainTextResponse)
    def get_unsubscribe(email: str, account: str) -> str:
        """Public (no auth) CAN-SPAM opt-out. Adds the address to suppression."""
        unsubscribe(deps.uow_factory_for(account), account, email)
        return "You have been unsubscribed. You will receive no further emails."

    @app.get("/packs", response_model=list[PackDTO])
    def get_packs() -> list[PackDTO]:
        return [
            PackDTO(id=p.id, name=p.name, credits=p.credits, price_cents=p.price_cents)
            for p in list_active_packs(deps.uow_factory_for(""))
        ]

    @app.post("/checkout", response_model=CheckoutResponse)
    def post_checkout(
        body: CheckoutRequest, account_id: str = Depends(require_account)
    ) -> CheckoutResponse:
        try:
            session = start_checkout(
                deps.uow_factory_for(account_id), deps.payments,
                account_id=account_id, pack_id=body.pack_id,
                success_url=deps.config.checkout_success_url,
                cancel_url=deps.config.checkout_cancel_url,
            )
        except PackNotFoundError:
            raise HTTPException(status_code=404, detail="pack not found")
        return CheckoutResponse(checkout_url=session.url)

    @app.post("/webhooks/stripe")
    async def stripe_webhook(request: Request) -> dict:
        """Public, unauthenticated (as Stripe webhooks are). Idempotent on event.id."""
        payload = await request.body()
        signature = request.headers.get("stripe-signature")
        try:
            granted = handle_webhook(
                deps.uow_factory_for, deps.payments, payload, signature
            )
        except ValueError:
            # Bad signature / unparseable payload.
            raise HTTPException(status_code=400, detail="invalid webhook")
        return {"granted": granted}

    return app
