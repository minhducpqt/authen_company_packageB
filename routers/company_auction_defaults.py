from __future__ import annotations

import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/account/company", tags=["company-auction-defaults"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")

REGISTRATION_MODE_LABELS = {
    "NORMAL": "Đấu lô (mặc định)",
    "GROUP_AUCTION": "Đấu nhóm",
}

AUCTION_MODE_LABELS = {
    "PER_LOT": "Theo cả lô",
    "PER_SQM": "Theo m²",
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


@router.get("/{company_code}/auction-defaults", response_class=HTMLResponse)
async def company_auction_defaults_page(request: Request, company_code: str):
    me = await _me(request)
    if not me:
        return RedirectResponse(
            url=f"/login?next=/account/company/{quote(company_code)}/auction-defaults",
            status_code=303,
        )
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return RedirectResponse(url="/account?err=forbidden", status_code=303)

    cfg = {
        "company_code": company_code,
        "registration_mode": "NORMAL",
        "registration_mode_label": REGISTRATION_MODE_LABELS["NORMAL"],
        "is_configured": False,
        "auction_mode": "PER_LOT",
        "auction_mode_label": AUCTION_MODE_LABELS["PER_LOT"],
        "is_auction_mode_configured": False,
    }
    load_err = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.get(
                f"/api/v1/admin/companies/{company_code}/project-defaults",
                headers=_headers(request),
            )
            if r.status_code == 200:
                cfg = r.json()
            else:
                load_err = f"Không tải được cấu hình (HTTP {r.status_code})."
    except Exception as exc:
        load_err = str(exc)

    return templates.TemplateResponse(
        "pages/account/company_auction_defaults.html",
        {
            "request": request,
            "title": f"Cấu hình đấu giá — {company_code}",
            "me": me,
            "company_code": company_code,
            "cfg": cfg,
            "registration_mode_labels": REGISTRATION_MODE_LABELS,
            "auction_mode_labels": AUCTION_MODE_LABELS,
            "load_err": load_err,
            "msg": request.query_params.get("msg"),
            "err": request.query_params.get("err"),
        },
    )


@router.post("/{company_code}/auction-defaults")
async def company_auction_defaults_save(
    request: Request,
    company_code: str,
    registration_mode: str = Form(...),
    auction_mode: str = Form(...),
):
    me = await _me(request)
    if not me:
        return RedirectResponse(
            url=f"/login?next=/account/company/{quote(company_code)}/auction-defaults",
            status_code=303,
        )
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return RedirectResponse(url="/account?err=forbidden", status_code=303)

    mode = (registration_mode or "").strip().upper()
    auc = (auction_mode or "").strip().upper()
    if mode not in REGISTRATION_MODE_LABELS or auc not in AUCTION_MODE_LABELS:
        return RedirectResponse(
            url=f"/account/company/{quote(company_code)}/auction-defaults?err=save_failed",
            status_code=303,
        )

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.put(
                f"/api/v1/admin/companies/{company_code}/project-defaults",
                json={"registration_mode": mode, "auction_mode": auc},
                headers=_headers(request),
            )
        if r.status_code != 200:
            return RedirectResponse(
                url=f"/account/company/{quote(company_code)}/auction-defaults?err=save_failed",
                status_code=303,
            )
    except Exception:
        return RedirectResponse(
            url=f"/account/company/{quote(company_code)}/auction-defaults?err=save_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/account/company/{quote(company_code)}/auction-defaults?msg=saved",
        status_code=303,
    )
