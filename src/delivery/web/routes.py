"""Server-rendered Radar feed routes. Form bodies are parsed with the stdlib
(urlencoded), so no python-multipart dependency. Auth is the signed cookie from
src/delivery/auth.py. Successful scans use Post/Redirect/Get to avoid re-spend on
refresh; errors re-render the dashboard inline.
"""
from __future__ import annotations

from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.application import credits
from src.application.pitch import LeadNotFoundError, draft_pitch
from src.delivery.auth import (
    COOKIE_NAME,
    SESSION_TTL_SECONDS,
    make_session_cookie,
    password_ok,
    resolve_account,
)
from src.delivery.deps import Deps, ScanParams, execute_scan
from src.delivery.web import views
from src.domain.errors import ConfirmationRequiredError, InsufficientCreditsError


def create_web_router(deps: Deps) -> APIRouter:
    router = APIRouter()
    config = deps.config

    async def _form(request: Request) -> dict[str, str]:
        body = await request.body()
        return {k: v[0] for k, v in parse_qs(body.decode("utf-8")).items()}

    def _tenant_account_id() -> str | None:
        with deps.uow_factory_for(config.tenant_owner_user_id)() as uow:
            acct = uow.accounts.get_by_owner(config.tenant_owner_user_id)
            return acct.id if acct else None

    def _render_dashboard(account_id, message=None, error=None) -> HTMLResponse:
        with deps.uow_factory_for(account_id)() as uow:
            acct = uow.accounts.get(account_id)
            balance = credits.balance(uow, account_id)
            leads = uow.leads.list_for_account(account_id)
        leads.sort(key=lambda l: l.rank, reverse=True)
        name = acct.name if acct else account_id
        return HTMLResponse(views.render_dashboard(name, balance, leads, message, error))

    @router.get("/login", response_class=HTMLResponse)
    def login_form() -> str:
        return views.render_login()

    @router.post("/login")
    async def login_submit(request: Request):
        form = await _form(request)
        if not password_ok(config, form.get("password", "")):
            return HTMLResponse(views.render_login("Wrong password."), status_code=401)
        account_id = _tenant_account_id()
        if not account_id:
            return HTMLResponse(
                views.render_login("Tenant not provisioned — check server startup."),
                status_code=500,
            )
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(
            COOKIE_NAME,
            make_session_cookie(config.session_secret, account_id),
            httponly=True,
            samesite="lax",
            max_age=SESSION_TTL_SECONDS,
        )
        return resp

    @router.get("/logout")
    def logout():
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(COOKIE_NAME)
        return resp

    @router.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        account_id = resolve_account(config, request)
        if not account_id:
            return RedirectResponse("/login", status_code=303)
        return _render_dashboard(account_id)

    @router.post("/scan")
    async def scan(request: Request):
        account_id = resolve_account(config, request)
        if not account_id:
            return RedirectResponse("/login", status_code=303)
        form = await _form(request)
        try:
            limit = int(form.get("limit", "10"))
        except ValueError:
            return _render_dashboard(account_id, error="Limit must be a number.")
        keywords = [k.strip() for k in form.get("keywords", "").split(",") if k.strip()]
        params = ScanParams(
            niche=form.get("niche", ""),
            city=form.get("city", ""),
            limit=limit,
            confirmed=form.get("confirmed") == "1",
            keywords=keywords,
        )
        try:
            execute_scan(deps, account_id, params)
        except ConfirmationRequiredError as e:
            return _render_dashboard(
                account_id, error=f"Tick ‘confirm spend’ — this costs {e.estimated_cost} credits."
            )
        except InsufficientCreditsError as e:
            return _render_dashboard(
                account_id,
                error=f"Not enough credits: need {e.required}, have {e.available}.",
            )
        except ValueError as e:
            return _render_dashboard(account_id, error=str(e))
        # Post/Redirect/Get so a refresh doesn't re-run (and re-bill) the scan.
        return RedirectResponse("/", status_code=303)

    @router.post("/leads/{lead_id}/draft")
    def draft(lead_id: str, request: Request):
        account_id = resolve_account(config, request)
        if not account_id:
            return RedirectResponse("/login", status_code=303)
        try:
            draft_pitch(
                deps.uow_factory_for(account_id),
                deps.ai,
                account_id=account_id,
                lead_id=lead_id,
                credit_per_pitch=config.credit_per_pitch,
            )
        except LeadNotFoundError:
            return _render_dashboard(account_id, error="Lead not found.")
        except InsufficientCreditsError as e:
            return _render_dashboard(
                account_id,
                error=f"Not enough credits to draft: need {e.required}, have {e.available}.",
            )
        return RedirectResponse("/", status_code=303)

    return router
