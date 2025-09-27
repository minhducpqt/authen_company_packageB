# web/routers/settings/company.py  (đặt cùng nơi bạn đã để bank-accounts)
from __future__ import annotations
import os
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/settings/company", tags=["settings:company"])
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

def _is_company_admin(me: dict) -> bool:
    roles = (me or {}).get("roles") or []
    # coi SUPER là admin tối cao
    return ("SUPER" in roles) or ("ADMIN" in roles)

async def _get_json(client: httpx.AsyncClient, url: str, headers: dict):
    r = await client.get(url, headers=headers)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None

async def _put_json(client: httpx.AsyncClient, url: str, headers: dict, payload: dict):
    r = await client.put(url, headers=headers, json=payload)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None

@router.get("", response_class=HTMLResponse)
async def company_profile_page(request: Request):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse("/login?next=" + quote("/settings/company"), status_code=303)

    can_edit = _is_company_admin(me)
    data = {}
    load_err: Optional[str] = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            st, j = await _get_json(client, "/api/v1/company/profile", {"Authorization": f"Bearer {token}"})
            if st == 200 and isinstance(j, dict):
                data = j
            else:
                load_err = f"Không tải được thông tin công ty (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/settings/company_profile.html",
        {
            "request": request,
            "title": "Thiết lập / Thông tin công ty",
            "me": me,
            "data": data,
            "can_edit": can_edit,
            "load_err": load_err,
            "saved": request.query_params.get("saved"),
        },
    )

@router.post("", response_class=HTMLResponse)
async def company_profile_save(
    request: Request,
    name: str = Form(""),
    tax_code: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    logo_url: str = Form(""),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse("/login?next=" + quote("/settings/company"), status_code=303)

    # chỉ ADMIN/SUPER được cập nhật
    if not _is_company_admin(me):
        return RedirectResponse("/settings/company?saved=forbidden", status_code=303)

    payload = {
        "name": (name or "").strip() or None,
        "tax_code": (tax_code or "").strip() or None,
        "email": (email or "").strip() or None,
        "phone": (phone or "").strip() or None,
        "address": (address or "").strip() or None,
        "logo_url": (logo_url or "").strip() or None,
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            st, _ = await _put_json(
                client, "/api/v1/company/profile",
                {"Authorization": f"Bearer {token}"}, payload
            )
            if st == 200:
                return RedirectResponse("/settings/company?saved=1", status_code=303)
            else:
                return RedirectResponse(f"/settings/company?saved=err{st}", status_code=303)
    except Exception:
        return RedirectResponse("/settings/company?saved=error", status_code=303)
