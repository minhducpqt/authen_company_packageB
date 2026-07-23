from __future__ import annotations

import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/account/company", tags=["otp-admin"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")


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


async def _load_otp_page(request: Request, company_code: str, msg: str | None = None, err: str | None = None):
    me = await _me(request)
    if not me:
        return RedirectResponse(url=f"/login?next=/account/company/{quote(company_code)}/otp", status_code=303)
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return RedirectResponse(url="/account?err=forbidden", status_code=303)

    h = _headers(request)
    settings = {"company_code": company_code, "otp_enabled": False, "apply_to": "WEB"}
    policies = []
    telegram_recipients = []
    sms_recipients = []
    challenges = []
    load_err = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.get(f"/api/v1/admin/companies/{company_code}/otp/settings", headers=h)
            if r.status_code == 200:
                settings = r.json()

            r = await client.get(f"/api/v1/admin/companies/{company_code}/otp/policies", headers=h)
            if r.status_code == 200:
                policies = (r.json() or {}).get("items") or []

            r = await client.get(
                f"/api/v1/admin/companies/{company_code}/otp/recipients",
                headers=h,
                params={"channel": "TELEGRAM"},
            )
            if r.status_code == 200:
                telegram_recipients = (r.json() or {}).get("items") or []

            r = await client.get(
                f"/api/v1/admin/companies/{company_code}/otp/recipients",
                headers=h,
                params={"channel": "SMS"},
            )
            if r.status_code == 200:
                sms_recipients = (r.json() or {}).get("items") or []

            r = await client.get(
                f"/api/v1/admin/companies/{company_code}/otp/challenges",
                headers=h,
                params={"limit": 30},
            )
            if r.status_code == 200:
                challenges = (r.json() or {}).get("items") or []
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/account/company_otp_config.html",
        {
            "request": request,
            "company_code": company_code,
            "settings": settings,
            "policies": policies,
            "telegram_recipients": telegram_recipients,
            "sms_recipients": sms_recipients,
            "challenges": challenges,
            "msg": msg,
            "err": err,
            "load_err": load_err,
        },
    )


@router.get("/{company_code}/otp", response_class=HTMLResponse)
async def company_otp_config_page(request: Request, company_code: str, msg: str | None = None, err: str | None = None):
    return await _load_otp_page(request, company_code, msg=msg, err=err)


@router.post("/{company_code}/otp/settings")
async def company_otp_settings_save(
    request: Request,
    company_code: str,
    otp_enabled: str = Form("0"),
):
    h = _headers(request)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        r = await client.put(
            f"/api/v1/admin/companies/{company_code}/otp/settings",
            headers=h,
            json={"otp_enabled": otp_enabled in ("1", "true", "on")},
        )
        st = r.status_code
    q = "msg=settings_saved" if st == 200 else "err=settings_failed"
    return RedirectResponse(url=f"/account/company/{quote(company_code)}/otp?{q}", status_code=303)


@router.post("/{company_code}/otp/policies/{purpose}")
async def company_otp_policy_save(
    request: Request,
    company_code: str,
    purpose: str,
    enabled: str = Form("0"),
    ttl_sec: int = Form(300),
    max_attempts: int = Form(5),
    max_resend: int = Form(3),
):
    h = _headers(request)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        r = await client.put(
            f"/api/v1/admin/companies/{company_code}/otp/policies/{purpose}",
            headers=h,
            json={
                "enabled": enabled in ("1", "true", "on"),
                "ttl_sec": ttl_sec,
                "max_attempts": max_attempts,
                "max_resend": max_resend,
                "otp_length": 6,
            },
        )
        st = r.status_code
    q = "msg=policy_saved" if st == 200 else "err=policy_failed"
    return RedirectResponse(url=f"/account/company/{quote(company_code)}/otp?{q}", status_code=303)


@router.post("/{company_code}/otp/recipients")
async def company_otp_recipient_create(
    request: Request,
    company_code: str,
    channel: str = Form("TELEGRAM"),
    target: str = Form(...),
    target_label: str = Form(""),
    purposes: str = Form("*"),
    priority: int = Form(1),
):
    h = _headers(request)
    plist = ["*"] if channel.upper() == "TELEGRAM" else ([p.strip() for p in purposes.split(",") if p.strip()] or ["*"])
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        r = await client.post(
            f"/api/v1/admin/companies/{company_code}/otp/recipients",
            headers=h,
            json={
                "channel": channel.upper(),
                "target": target.strip(),
                "target_label": target_label or None,
                "purposes": plist,
                "priority": priority,
                "is_active": True,
            },
        )
        st = r.status_code
    q = "msg=recipient_added" if st == 200 else "err=recipient_failed"
    return RedirectResponse(url=f"/account/company/{quote(company_code)}/otp?{q}", status_code=303)


@router.post("/{company_code}/otp/recipients/{recipient_id}/delete")
async def company_otp_recipient_delete(request: Request, company_code: str, recipient_id: int):
    h = _headers(request)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        r = await client.delete(
            f"/api/v1/admin/companies/{company_code}/otp/recipients/{recipient_id}",
            headers=h,
        )
        st = r.status_code
    q = "msg=recipient_deleted" if st == 200 else "err=recipient_delete_failed"
    return RedirectResponse(url=f"/account/company/{quote(company_code)}/otp?{q}", status_code=303)


@router.post("/{company_code}/otp/recipients/{recipient_id}/test")
async def company_otp_recipient_test(request: Request, company_code: str, recipient_id: int):
    h = _headers(request)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
        r = await client.post(
            f"/api/v1/admin/companies/{company_code}/otp/recipients/{recipient_id}/test",
            headers=h,
        )
        st = r.status_code
    q = "msg=test_sent" if st == 200 else "err=test_failed"
    return RedirectResponse(url=f"/account/company/{quote(company_code)}/otp?{q}", status_code=303)
