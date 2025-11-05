# routers/company_mailers.py
from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.templating import Jinja2Templates
import httpx
import os

# Tái sử dụng cùng cơ chế cookie như routers/account.py
from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates  # đã có sẵn trong project của bạn

router = APIRouter(tags=["company-mailers"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
# Bên account.py có cả biến môi trường ACCESS_COOKIE_NAME -> dùng lại để lấy cookie access
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")

def _auth_headers(request: Request) -> dict:
    """
    Lấy access token từ cookie (ưu tiên tên trong env, fallback ACCESS_COOKIE_NAME của middleware),
    rồi nhét vào Authorization Bearer để call Service A.
    """
    token = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    return {"Authorization": f"Bearer {token}"} if token else {}

# -------------------- PAGES --------------------

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

# -------------------- PROXIES -> Service A --------------------

@router.get("/api/v1/company-mailers")
async def proxy_list_mailers(request: Request, company_code: str | None = None):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers"
    params = {}
    if company_code:
        params["company_code"] = company_code
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params, headers=_auth_headers(request))
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return JSONResponse(r.json())

@router.post("/api/v1/company-mailers")
async def proxy_create_mailer(request: Request):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers"
    payload = await request.json()
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload, headers=_auth_headers(request))
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return JSONResponse(r.json(), status_code=r.status_code)

@router.put("/api/v1/company-mailers/{mailer_id}")
async def proxy_update_mailer(mailer_id: int, request: Request):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers/{mailer_id}"
    payload = await request.json()
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.put(url, json=payload, headers=_auth_headers(request))
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return JSONResponse(r.json())

@router.post("/api/v1/company-mailers/{mailer_id}/activate")
async def proxy_activate_mailer(mailer_id: int, request: Request):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers/{mailer_id}/activate"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, headers=_auth_headers(request))
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    return JSONResponse(r.json())

@router.delete("/api/v1/company-mailers/{mailer_id}")
async def proxy_delete_mailer(mailer_id: int, request: Request):
    url = f"{SERVICE_A_BASE_URL}/api/v1/admin/company-mailers/{mailer_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.delete(url, headers=_auth_headers(request))
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text)
    # Service A trả 204 No Content; B mirror 204 rỗng
    return JSONResponse(content={}, status_code=204)
