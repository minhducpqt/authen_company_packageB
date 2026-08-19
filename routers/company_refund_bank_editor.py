from __future__ import annotations

import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/account/company", tags=["company-refund-bank-editor"])

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


@router.get("/{company_code}/refund-bank-editor", response_class=HTMLResponse)
async def company_refund_bank_editor_page(request: Request, company_code: str):
    me = await _me(request)
    if not me:
        return RedirectResponse(
            url=f"/login?next=/account/company/{quote(company_code)}/refund-bank-editor",
            status_code=303,
        )
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return RedirectResponse(url="/account?err=forbidden", status_code=303)

    cfg = {"company_code": company_code, "configured": False, "editor": None}
    users = []
    load_err = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            headers = _headers(request)
            r = await client.get(
                f"/api/v1/admin/companies/{company_code}/refund-bank-editor",
                headers=headers,
            )
            if r.status_code == 200:
                cfg = r.json()
            else:
                load_err = f"Không tải được cấu hình (HTTP {r.status_code})."

            ru = await client.get(
                f"/api/v1/admin/users?company_code={quote(company_code)}&page=1&size=100",
                headers=headers,
            )
            if ru.status_code == 200:
                data = ru.json()
                raw = data.get("data", data) if isinstance(data, dict) else []
                users = [
                    u for u in (raw or [])
                    if (u.get("role") or "").upper() == "COMPANY_ADMIN" and u.get("is_active")
                ]
    except Exception as exc:
        load_err = str(exc)

    return templates.TemplateResponse(
        "pages/account/company_refund_bank_editor.html",
        {
            "request": request,
            "title": f"Sửa STK hoàn tiền — {company_code}",
            "me": me,
            "company_code": company_code,
            "cfg": cfg,
            "users": users,
            "load_err": load_err,
            "msg": request.query_params.get("msg"),
            "err": request.query_params.get("err"),
        },
    )


@router.post("/{company_code}/refund-bank-editor")
async def company_refund_bank_editor_save(
    request: Request,
    company_code: str,
    user_id: str = Form(""),
):
    me = await _me(request)
    if not me:
        return RedirectResponse(
            url=f"/login?next=/account/company/{quote(company_code)}/refund-bank-editor",
            status_code=303,
        )
    if (me.get("role") or "").upper() != "SUPER_ADMIN":
        return RedirectResponse(url="/account?err=forbidden", status_code=303)

    base = f"/account/company/{quote(company_code)}/refund-bank-editor"
    uid = (user_id or "").strip()

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            headers = _headers(request)
            if not uid:
                r = await client.delete(
                    f"/api/v1/admin/companies/{company_code}/refund-bank-editor",
                    headers=headers,
                )
            else:
                r = await client.put(
                    f"/api/v1/admin/companies/{company_code}/refund-bank-editor",
                    json={"user_id": int(uid)},
                    headers=headers,
                )
            if r.status_code not in (200, 204):
                return RedirectResponse(url=f"{base}?err=save_failed", status_code=303)
    except Exception:
        return RedirectResponse(url=f"{base}?err=save_failed", status_code=303)

    return RedirectResponse(url=f"{base}?msg=saved", status_code=303)
