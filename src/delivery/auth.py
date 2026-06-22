"""Authentication for the delivery layer.

Two modes (config.auth_mode):
- "dev_header": trusts an ``X-Account-Id`` header. For local/dev and the API tests
  only — never enable in production.
- "session": a password login sets a signed cookie holding the tenant account id.
  This is the production path for the tenant-#1 MVP; Supabase JWT verification can
  replace it here later.

The signed cookie is implemented with the standard library (HMAC-SHA256) — no extra
dependency. Payload is base64(JSON) with an issued-at timestamp; the signature is
verified in constant time on every request.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import Header, HTTPException, Request

COOKIE_NAME = "lc_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 1 week

from src.config import Config


def password_ok(config: Config, candidate: str) -> bool:
    """Constant-time password check against the configured login password."""
    if not config.login_password:
        return False
    return hmac.compare_digest(candidate, config.login_password)


def _sign(secret: str, payload_b64: bytes) -> str:
    return hmac.new(secret.encode(), payload_b64, hashlib.sha256).hexdigest()


def make_session_cookie(secret: str, account_id: str) -> str:
    payload = json.dumps({"account_id": account_id, "iat": int(time.time())}).encode()
    b64 = base64.urlsafe_b64encode(payload)
    return f"{b64.decode()}.{_sign(secret, b64)}"


def read_session_cookie(secret: str, raw: str | None) -> str | None:
    if not raw or "." not in raw:
        return None
    b64, sig = raw.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(secret, b64.encode())):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(b64))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(time.time()) - int(data.get("iat", 0)) > SESSION_TTL_SECONDS:
        return None
    return data.get("account_id")


def resolve_account(config: Config, request: Request) -> str | None:
    """Return the current account id, or None if unauthenticated. Never raises."""
    if config.auth_mode == "session":
        return read_session_cookie(config.session_secret, request.cookies.get(COOKIE_NAME))
    return request.headers.get("x-account-id")


def make_current_account(config: Config):
    """FastAPI dependency for JSON routes: resolves the account or raises 401."""

    def current_account(
        request: Request, x_account_id: str | None = Header(default=None)
    ) -> str:
        account_id = resolve_account(config, request)
        if not account_id:
            detail = (
                "not authenticated"
                if config.auth_mode == "session"
                else "missing X-Account-Id header"
            )
            raise HTTPException(status_code=401, detail=detail)
        return account_id

    return current_account
