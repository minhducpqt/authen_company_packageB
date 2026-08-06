from __future__ import annotations

import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/account/company", tags=["telegram-notify-admin"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")

EVENT_LABELS = {
    "customer_new": "KH đăng ký mới",
    "dossier_paid": "Mua hồ sơ đã thanh toán",
    "deposit_paid": "Đặt cọc đã thanh toán",
}


async def _me(request: Request) -> dict | None:
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    if not acc:
        return None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            r = await client.get("/auth/me", headers={"Authorization": f"Bearer {acc}"})
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def _headers(request: Request) -> dict:
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    return {"Authorization": f"Bearer {acc}"} if acc else {}


async def _require_super(request: Request, company_code: str):
    me = await _me(request)
    if not me:
        return None, RedirectResponse(
            url=f"/login?next=/account/company/{quote(company_code)}/telegram-notify",
            status_code=303,
        )
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return None, RedirectResponse(url="/account?err=forbidden", status_code=303)
    return me, None


@router.get("/{company_code}/telegram-notify", response_class=HTMLResponse)
async def company_telegram_notify_page(
    request: Request,
    company_code: str,
    msg: str | None = None,
    err: str | None = None,
):
    me, redir = await _require_super(request, company_code)
    if redir:
        return redir

    items = []
    items_by_event: dict[str, dict] = {}
    load_err = None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.get(
                f"/api/v1/admin/companies/{company_code}/telegram-notify",
                headers=_headers(request),
            )
            if r.status_code == 200:
                items = (r.json() or {}).get("items") or []
                items_by_event = {it["event"]: it for it in items if it.get("event")}
            else:
                load_err = f"Không tải được cấu hình (HTTP {r.status_code})."
    except Exception as exc:
        load_err = str(exc)

    return templates.TemplateResponse(
        "pages/account/company_telegram_notify.html",
        {
            "request": request,
            "title": f"Telegram thông báo — {company_code}",
            "me": me,
            "company_code": company_code,
            "items": items,
            "items_by_event": items_by_event,
            "event_labels": EVENT_LABELS,
            "load_err": load_err,
            "msg": msg,
            "err": err,
        },
    )


@router.post("/{company_code}/telegram-notify")
async def company_telegram_notify_save(request: Request, company_code: str):
    _, redir = await _require_super(request, company_code)
    if redir:
        return redir

    form = await request.form()
    channels: dict[str, dict] = {}
    for ev in EVENT_LABELS:
        target = (form.get(f"target_{ev}") or "").strip()
        enabled = form.get(f"enabled_{ev}") in ("1", "on", "true")
        channels[ev] = {"target": target, "is_enabled": enabled}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.put(
                f"/api/v1/admin/companies/{company_code}/telegram-notify",
                headers=_headers(request),
                json={"channels": channels},
            )
        if r.status_code != 200:
            return RedirectResponse(
                url=f"/account/company/{quote(company_code)}/telegram-notify?err=save_failed",
                status_code=303,
            )
    except Exception:
        return RedirectResponse(
            url=f"/account/company/{quote(company_code)}/telegram-notify?err=save_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/account/company/{quote(company_code)}/telegram-notify?msg=saved",
        status_code=303,
    )


@router.post("/{company_code}/telegram-notify/{event}/test")
async def company_telegram_notify_test(request: Request, company_code: str, event: str):
    _, redir = await _require_super(request, company_code)
    if redir:
        return redir

    if event not in EVENT_LABELS:
        return RedirectResponse(
            url=f"/account/company/{quote(company_code)}/telegram-notify?err=test_failed",
            status_code=303,
        )

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.post(
                f"/api/v1/admin/companies/{company_code}/telegram-notify/{event}/test",
                headers=_headers(request),
            )
        if r.status_code != 200:
            return RedirectResponse(
                url=f"/account/company/{quote(company_code)}/telegram-notify?err=test_failed",
                status_code=303,
            )
    except Exception:
        return RedirectResponse(
            url=f"/account/company/{quote(company_code)}/telegram-notify?err=test_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/account/company/{quote(company_code)}/telegram-notify?msg=test_sent&event={quote(event)}",
        status_code=303,
    )
