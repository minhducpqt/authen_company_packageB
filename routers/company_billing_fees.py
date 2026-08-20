from __future__ import annotations

import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/account/company", tags=["company-billing-fees"])

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


@router.get("/{company_code}/billing-fees", response_class=HTMLResponse)
async def company_billing_fees_page(request: Request, company_code: str):
    me = await _me(request)
    if not me:
        return RedirectResponse(
            url=f"/login?next=/account/company/{quote(company_code)}/billing-fees",
            status_code=303,
        )
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return RedirectResponse(url="/account?err=forbidden", status_code=303)

    return templates.TemplateResponse(
        "pages/account/company_billing_fees.html",
        {
            "request": request,
            "title": f"Cấu hình chi phí — {company_code.upper()}",
            "company_code": company_code,
        },
    )
