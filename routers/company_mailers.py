# routers/company_mailers.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

# Reuse same cookie name logic as account router/middleware
from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME as MIDDLEWARE_ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(tags=["company-mailers"])

# ---------- Config ----------
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824").rstrip("/")
ACCESS_COOKIE_ENV = os.getenv("ACCESS_COOKIE_NAME")  # optional override
HIDE_APP_PASSWORD = os.getenv("HIDE_MAILER_APP_PASSWORD", "1") not in ("0", "false", "False")

HTTPX_TIMEOUT_GET = float(os.getenv("HTTPX_TIMEOUT_GET", "10"))
HTTPX_TIMEOUT_WRITE = float(os.getenv("HTTPX_TIMEOUT_WRITE", "15"))

def _auth_headers(request: Request) -> Dict[str, str]:
    """
    Lấy access token từ cookie (ưu tiên env ACCESS_COOKIE_NAME, sau đó đến middleware ACCESS_COOKIE_NAME),
    rồi đưa vào Authorization Bearer để call Service A.
    """
    cookie_name = ACCESS_COOKIE_ENV or MIDDLEWARE_ACCESS_COOKIE_NAME
    token = request.cookies.get(cookie_name) or request.cookies.get(MIDDLEWARE_ACCESS_COOKIE_NAME)
    return {"Authorization": f"Bearer {token}"} if token else {}

# ==================== PAGES ====================

@router.get("/account/company/{company_code}/email", response_class=HTMLResponse)
async def company_email_page(company_code: str, request: Request):
    """
    Trang UI cấu hình email cho một công ty.
    Template: templates/pages/account/company_email_config.html
    """
    return templates.TemplateResponse(
        "pages/account/company_email_config.html",
        {"request": request, "company_code": company_code}
    )

# ==================== PROXIES -> Service A (admin) ====================

@router.get("/api/v1/company-mailers")
async def proxy_list_mailers(request: Request, company_code: Optional[str] = None):
    """
    Proxy sang Service A: GET /api/v1/admin/company-mailers
    - Optionally filter theo company_code
    - Ẩn app_password ở response để tránh lộ trên UI/FE
    """
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers"
    params: Dict[str, Any] = {}
    if company_code:
        params["company_code"] = company_code

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_GET) as client:
        r = await client.get(url, params=params, headers=_auth_headers(request))

    if r.status_code >= 400:
        # Forward nguyên văn lỗi từ Service A
        raise HTTPException(status_code=r.status_code, detail=r.text)

    data = r.json()
    if HIDE_APP_PASSWORD:
        items = data.get("items", [])
        for it in items:
            it.pop("app_password", None)
        return JSONResponse({"items": items})

    return JSONResponse(data)


@router.post("/api/v1/company-mailers")
async def proxy_create_mailer(request: Request):
    """
    Proxy sang Service A: POST /api/v1/admin/company-mailers
    """
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers"
    payload = await request.json()

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_WRITE) as client:
        r = await client.post(url, json=payload, headers=_auth_headers(request))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return JSONResponse(r.json(), status_code=r.status_code)


@router.put("/api/v1/company-mailers/{mailer_id}")
async def proxy_update_mailer(mailer_id: int, request: Request):
    """
    Proxy sang Service A: PUT /api/v1/admin/company-mailers/{mailer_id}
    """
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers/{mailer_id}"
    payload = await request.json()

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_WRITE) as client:
        r = await client.put(url, json=payload, headers=_auth_headers(request))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    data = r.json()
    if HIDE_APP_PASSWORD and isinstance(data, dict):
        # Nếu Service A trả về object có chứa app_password
        data.pop("app_password", None)
    return JSONResponse(data)


@router.post("/api/v1/company-mailers/{mailer_id}/activate")
async def proxy_activate_mailer(mailer_id: int, request: Request):
    """
    Proxy sang Service A: POST /api/v1/admin/company-mailers/{mailer_id}/activate
    """
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers/{mailer_id}/activate"

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_GET) as client:
        r = await client.post(url, headers=_auth_headers(request))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    data = r.json()
    if HIDE_APP_PASSWORD and isinstance(data, dict):
        # Trường hợp Service A trả về active mailer có app_password
        if "active" in data and isinstance(data["active"], dict):
            data["active"].pop("app_password", None)
        else:
            data.pop("app_password", None)
    return JSONResponse(data)


@router.delete("/api/v1/company-mailers/{mailer_id}")
async def proxy_delete_mailer(mailer_id: int, request: Request):
    """
    Proxy sang Service A: DELETE /api/v1/admin/company-mailers/{mailer_id}
    Mirror 204 No Content.
    """
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers/{mailer_id}"

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT_GET) as client:
        r = await client.delete(url, headers=_auth_headers(request))

    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    # Service A trả 204, mirror lại 204
    return JSONResponse(content={}, status_code=204)
