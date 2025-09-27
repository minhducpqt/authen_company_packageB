from __future__ import annotations
import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/settings/company", tags=["settings:company"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


async def _get_json(client: httpx.AsyncClient, url: str, headers: dict):
    r = await client.get(url, headers=headers)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None

async def _put_json(client: httpx.AsyncClient, url: str, headers: dict, payload: dict | None):
    r = await client.put(url, headers=headers, json=payload or {})
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


@router.get("", response_class=HTMLResponse)
async def company_info(request: Request):
    """
    Hiển thị form cấu hình công ty hiện tại.
    Service A hiện có:
      - GET /api/v1/admin/companies (list) -> lọc theo company_code của user
      - PUT /api/v1/admin/companies/{company_id} -> cập nhật
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote('/settings/company')}", status_code=303)

    cc = me.get("company_code")
    if not cc:
        return RedirectResponse(url="/account?err=no_company_code", status_code=303)

    company = None
    load_err = None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            st, data = await _get_json(client, "/api/v1/admin/companies?page=1&size=200", {"Authorization": f"Bearer {token}"})
            if st == 200 and isinstance(data, dict):
                arr = data.get("data", data) or []
                company = next((c for c in arr if (c.get("company_code") or "").lower() == cc.lower()), None)
            else:
                load_err = f"Không tải được thông tin công ty (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/settings/company/info.html",
        {
            "request": request,
            "title": "Thiết lập / Thông tin công ty",
            "me": me,
            "company": company,
            "load_err": load_err,
        },
    )


@router.post("/save")
async def company_save(
    request: Request,
    name: str = Form(""),
    tax_code: str = Form(""),
    address: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    logo: str = Form(""),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/settings/company", status_code=303)

    cc = me.get("company_code") or ""
    # lấy company_id qua list
    company_id = None
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
        st, data = await _get_json(client, "/api/v1/admin/companies?page=1&size=200", {"Authorization": f"Bearer {token}"})
        if st == 200 and isinstance(data, dict):
            for c in (data.get("data", data) or []):
                if (c.get("company_code") or "").lower() == cc.lower():
                    company_id = c.get("id")
                    break

        if not company_id:
            return RedirectResponse(url="/settings/company?err=not_found", status_code=303)

        payload = {
            "name": (name or "").strip() or None,
            "tax_code": (tax_code or "").strip() or None,
            "address": (address or "").strip() or None,
            "phone": (phone or "").strip() or None,
            "email": (email or "").strip() or None,
            "logo": (logo or "").strip() or None,  # nếu Service A hỗ trợ, không thì bỏ qua
        }
        # loại None để không ghi đè vô tình
        payload = {k: v for k, v in payload.items() if v is not None}

        st2, _ = await _put_json(client, f"/api/v1/admin/companies/{company_id}", {"Authorization": f"Bearer {token}"}, payload)

    to = "/settings/company?msg=saved" if st2 == 200 else "/settings/company?err=save_failed"
    return RedirectResponse(url=to, status_code=303)
