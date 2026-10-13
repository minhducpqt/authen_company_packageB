from __future__ import annotations

import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/account/company", tags=["company-customer-portal-hub"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")
HUB_HOME = os.getenv("CUSTOMER_PORTAL_HUB_URL", "https://khachhang.daugiathongminh.vn/")


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


@router.get("/{company_code}/customer-portal-hub", response_class=HTMLResponse)
async def customer_portal_hub_page(request: Request, company_code: str):
    me = await _me(request)
    if not me:
        return RedirectResponse(
            url=f"/login?next=/account/company/{quote(company_code)}/customer-portal-hub",
            status_code=303,
        )
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return RedirectResponse(url="/account?err=forbidden", status_code=303)

    cfg = {"company_code": company_code, "listed_on_hub": True, "is_configured": False}
    load_err = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.get(
                f"/api/v1/admin/companies/{company_code}/customer-portal-hub-listing",
                headers=_headers(request),
            )
            if r.status_code == 200:
                cfg = r.json()
            else:
                load_err = f"Không tải được cấu hình (HTTP {r.status_code})."
    except Exception as exc:
        load_err = str(exc)

    return templates.TemplateResponse(
        "pages/account/company_customer_portal_hub.html",
        {
            "request": request,
            "title": f"Cổng hub — {company_code}",
            "me": me,
            "company_code": company_code,
            "cfg": cfg,
            "hub_home": HUB_HOME,
            "load_err": load_err,
            "msg": request.query_params.get("msg"),
            "err": request.query_params.get("err"),
        },
    )


@router.post("/{company_code}/customer-portal-hub")
async def customer_portal_hub_save(
    request: Request,
    company_code: str,
    listed_on_hub: str = Form("0"),
):
    me = await _me(request)
    if not me:
        return RedirectResponse(
            url=f"/login?next=/account/company/{quote(company_code)}/customer-portal-hub",
            status_code=303,
        )
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return RedirectResponse(url="/account?err=forbidden", status_code=303)

    listed = (listed_on_hub or "").strip().lower() in ("1", "true", "on", "yes")

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.put(
                f"/api/v1/admin/companies/{company_code}/customer-portal-hub-listing",
                json={"listed_on_hub": listed},
                headers=_headers(request),
            )
        if r.status_code != 200:
            return RedirectResponse(
                url=f"/account/company/{quote(company_code)}/customer-portal-hub?err=save_failed",
                status_code=303,
            )
    except Exception:
        return RedirectResponse(
            url=f"/account/company/{quote(company_code)}/customer-portal-hub?err=save_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/account/company/{quote(company_code)}/customer-portal-hub?msg=saved",
        status_code=303,
    )
