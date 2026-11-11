"""Cấu hình và kiểm tra tra cứu tài khoản hoàn cọc. Service B chỉ gọi Service A."""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.auth import fetch_me, get_access_token
from utils.templates import templates

router = APIRouter(tags=["refund-account-lookup"])
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _require_super(request: Request):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return None, RedirectResponse(
            url=f"/login?next={quote('/settings/refund-account-lookup')}",
            status_code=303,
        )
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return None, RedirectResponse(url="/account", status_code=303)
    return token, None


@router.get("/settings/refund-account-lookup", response_class=HTMLResponse)
async def refund_lookup_setting_page(request: Request):
    token, denied = await _require_super(request)
    if denied:
        return denied
    enabled = False
    load_err = None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            response = await client.get(
                "/api/v1/admin/refund-account-lookup",
                headers=_headers(token),
            )
        if response.status_code == 200:
            enabled = bool((response.json() or {}).get("enabled"))
        else:
            load_err = "Chưa đọc được cấu hình. Hãy chạy make ensure trên Service A rồi thử lại."
    except httpx.HTTPError:
        load_err = "Không kết nối được Service A."
    return templates.TemplateResponse(
        "pages/settings/refund_account_lookup.html",
        {
            "request": request,
            "title": "Tra cứu STK hoàn cọc",
            "enabled": enabled,
            "load_err": load_err,
            "saved": request.query_params.get("saved") == "1",
        },
    )


@router.post("/settings/refund-account-lookup")
async def refund_lookup_setting_save(request: Request, enabled: str = Form("")):
    token, denied = await _require_super(request)
    if denied:
        return denied
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            response = await client.put(
                "/api/v1/admin/refund-account-lookup",
                headers=_headers(token),
                json={"enabled": enabled == "1"},
            )
        if response.status_code != 200:
            return RedirectResponse(
                url="/settings/refund-account-lookup?saved=0",
                status_code=303,
            )
    except httpx.HTTPError:
        return RedirectResponse(url="/settings/refund-account-lookup?saved=0", status_code=303)
    return RedirectResponse(url="/settings/refund-account-lookup?saved=1", status_code=303)


@router.get("/auction/refunds/lookup-mode")
async def refund_lookup_mode(request: Request):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"enabled": False}, status_code=401)
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            response = await client.get(
                "/api/v1/refund-account-lookup/mode",
                headers=_headers(token),
            )
        if response.status_code == 200:
            return JSONResponse(response.json())
    except httpx.HTTPError:
        pass
    return JSONResponse({"enabled": False})


@router.post("/auction/refunds/verify-accounts")
async def refund_lookup_verify(request: Request):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=120.0) as client:
            response = await client.post(
                "/api/v1/refund-account-lookup/verify",
                headers=_headers(token),
                json=payload if isinstance(payload, dict) else {},
            )
        try:
            body = response.json()
        except Exception:
            body = {"enabled": False, "items": []}
        return JSONResponse(body, status_code=response.status_code)
    except httpx.HTTPError:
        return JSONResponse(
            {"enabled": True, "items": [], "error": "unavailable"},
            status_code=503,
        )


@router.get("/customers/refund-account-lookup/mode")
async def customer_refund_lookup_mode(request: Request):
    return await refund_lookup_mode(request)


@router.post("/customers/refund-account-lookup")
async def customer_refund_lookup(request: Request):
    return await refund_lookup_verify(request)
