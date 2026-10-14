# fastapi_account_manager/middlewares/billing_nav_guard.py
"""Portal UI: billing-only navigation when company billing is LOCKED (no Service A changes)."""
from __future__ import annotations

import os
from urllib.parse import quote

import httpx
from starlette.responses import RedirectResponse

from utils.auth import get_access_token
from utils.billing_nav_lock import billing_status_nav_locked

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ROLE_COOKIE_NAME = os.getenv("ROLE_COOKIE_NAME", "user_role")
AUTH_TIMEOUT = float(os.getenv("AUTH_HTTP_TIMEOUT", "5.0"))

ALLOW_PREFIXES = (
    "/static/",
    "/favicon.ico",
    "/healthz",
    "/login",
    "/logout",
    "/account",
    "/billing",
    "/huong-dan",
    "/apis/mobile/",
)

ALLOW_EXACT = {"/healthz", "/logout", "/login"}


def _role(request) -> str:
    rc = request.cookies.get(ROLE_COOKIE_NAME)
    if rc:
        return rc.upper().strip()
    try:
        me = getattr(request.state, "auth_me", None) or {}
        if isinstance(me, dict):
            return str(me.get("role") or "").upper().strip()
    except Exception:
        pass
    return ""


def _path_allowed_when_locked(path: str) -> bool:
    if path in ALLOW_EXACT:
        return True
    return any(path.startswith(p) for p in ALLOW_PREFIXES)


def _is_admin_page_open(request) -> bool:
    """Mở trang SSR (HTML) — không gọi billing status cho /data, API proxy, POST, static."""
    if request.method not in ("GET", "HEAD"):
        return False
    path = request.url.path or "/"
    if path.startswith("/api/") or path.endswith("/data"):
        return False
    if path.startswith("/apis/mobile/"):
        return False
    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept and "text/html" not in accept:
        return False
    return True


async def _fetch_billing_status(access_token: str) -> dict | None:
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=AUTH_TIMEOUT) as client:
            r = await client.get(
                "/api/v1/billing/status",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if r.status_code != 200:
            return None
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception as e:
        print("[BILLING_NAV] status fetch error:", e)
        return None


async def billing_nav_guard_middleware(request, call_next):
    path = request.url.path or "/"

    try:
        request.state.billing_nav_locked = False
        request.state.billing_lock_detail = None
    except Exception:
        pass

    if any(path.startswith(p) for p in ("/static/", "/login", "/healthz")):
        return await call_next(request)

    if not _is_admin_page_open(request):
        return await call_next(request)

    token = get_access_token(request)
    if not token:
        return await call_next(request)

    role = _role(request)
    if role == "SUPER_ADMIN":
        return await call_next(request)

    status = await _fetch_billing_status(token)
    locked = billing_status_nav_locked(status)

    try:
        request.state.billing_nav_locked = locked
        request.state.billing_lock_detail = status if locked else None
    except Exception:
        pass

    if locked and not _path_allowed_when_locked(path):
        nxt = quote(path + (f"?{request.url.query}" if request.url.query else ""))
        return RedirectResponse(url=f"/billing?billing_locked=1&from={nxt}", status_code=303)

    return await call_next(request)
