from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME as MIDDLEWARE_ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(tags=["company-mailers"])

# ---------- Config ----------
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824").rstrip("/")
ACCESS_COOKIE_ENV = os.getenv("ACCESS_COOKIE_NAME")

HTTPX_TIMEOUT_GET = float(os.getenv("HTTPX_TIMEOUT_GET", "10"))
HTTPX_TIMEOUT_WRITE = float(os.getenv("HTTPX_TIMEOUT_WRITE", "15"))

MASKED_PASSWORD = "••••••••"


def _auth_headers(request: Request) -> Dict[str, str]:
    cookie_name = ACCESS_COOKIE_ENV or MIDDLEWARE_ACCESS_COOKIE_NAME
    token = request.cookies.get(cookie_name) or request.cookies.get(MIDDLEWARE_ACCESS_COOKIE_NAME)
    return {"Authorization": f"Bearer {token}"} if token else {}


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _decorate_mailer_item(item: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(item)

    raw_pw = _clean_str(d.get("app_password"))
    has_pw = bool(raw_pw)
    send_mode = (_clean_str(d.get("send_mode")) or "RELAY").upper()
    if send_mode not in {"AUTH", "RELAY"}:
        send_mode = "RELAY"

    d["has_app_password"] = has_pw
    d["app_password_masked"] = MASKED_PASSWORD if has_pw else ""
    d["send_mode"] = send_mode

    d.pop("app_password", None)
    return d


def _decorate_mailer_list_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    items = data.get("items", [])
    return {"items": [_decorate_mailer_item(it) for it in items]}


def _decorate_single_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(data)

    if "active" in d and isinstance(d["active"], dict):
        d["active"] = _decorate_mailer_item(d["active"])
        return d

    d.pop("app_password", None)
    return d


@router.get("/account/company/{company_code}/email", response_class=HTMLResponse)
async def company_email_page(company_code: str, request: Request):
    return templates.TemplateResponse(
        "pages/account/company_email_config.html",
        {"request": request, "company_code": company_code}
    )


@router.get("/api/v1/company-mailers")
async def proxy_list_mailers(request: Request, company_code: Optional[str] = None):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers"
    params: Dict[str, Any] = {}
    if company_code:
        params["company_code"] = company_code

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_GET) as client:
        r = await client.get(url, params=params, headers=_auth_headers(request))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    data = r.json()
    return JSONResponse(_decorate_mailer_list_payload(data))


@router.post("/api/v1/company-mailers")
async def proxy_create_mailer(request: Request):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers"
    payload = await request.json()

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_WRITE) as client:
        r = await client.post(url, json=payload, headers=_auth_headers(request))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return JSONResponse(r.json(), status_code=r.status_code)


@router.put("/api/v1/company-mailers/{mailer_id}")
async def proxy_update_mailer(mailer_id: int, request: Request):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers/{mailer_id}"
    payload = await request.json()

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_WRITE) as client:
        r = await client.put(url, json=payload, headers=_auth_headers(request))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    data = r.json()
    if isinstance(data, dict):
        return JSONResponse(_decorate_single_payload(data))
    return JSONResponse(data)


@router.post("/api/v1/company-mailers/{mailer_id}/activate")
async def proxy_activate_mailer(mailer_id: int, request: Request):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers/{mailer_id}/activate"

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_GET) as client:
        r = await client.post(url, headers=_auth_headers(request))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    data = r.json()
    if isinstance(data, dict):
        return JSONResponse(_decorate_single_payload(data))
    return JSONResponse(data)


@router.delete("/api/v1/company-mailers/{mailer_id}")
async def proxy_delete_mailer(mailer_id: int, request: Request):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers/{mailer_id}"

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_GET) as client:
        r = await client.delete(url, headers=_auth_headers(request))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return Response(status_code=204)