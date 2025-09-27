# routers/settings_company.py
from __future__ import annotations
import os
import httpx
from typing import Optional
from urllib.parse import quote

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

async def _put_json(client: httpx.AsyncClient, url: str, headers: dict, payload: dict):
    r = await client.put(url, headers=headers, json=payload)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None

def _is_company_admin(role: str | None) -> bool:
    return (role or "").upper() in ("COMPANY_ADMIN", "SUPER_ADMIN")

@router.get("", response_class=HTMLResponse)
async def company_profile_page(request: Request):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote('/settings/company')}", status_code=303)

    role = (me.get("role") or "").upper()
    can_edit = _is_company_admin(role)

    headers = {"Authorization": f"Bearer {token}"}
    item = None
    load_err = None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            st, data = await _get_json(client, "/api/v1/company/profile", headers)
            if st == 200 and isinstance(data, dict):
                item = data
            else:
                load_err = f"Không tải được thông tin công ty (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/settings/company/profile.html",
        {
            "request": request,
            "title": "Thiết lập / Thông tin công ty",
            "me": me,
            "item": item,
            "can_edit": can_edit,
            "load_err": load_err,
        },
    )

@router.post("/save")
async def company_profile_save(
    request: Request,
    name: str = Form(""),
    tax_code: str = Form(""),
    address: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/settings/company", status_code=303)

    role = (me.get("role") or "").upper()
    if not _is_company_admin(role):
        return RedirectResponse(url="/settings/company?err=forbidden", status_code=303)

    payload = {
        "name": (name or "").strip() or None,
        "tax_code": (tax_code or "").strip() or None,
        "address": (address or "").strip() or None,
        "phone": (phone or "").strip() or None,
        "email": (email or "").strip() or None,
    }

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            st, _ = await _put_json(client, "/api/v1/company/profile", headers, payload)
        to = "/settings/company?msg=saved" if st == 200 else "/settings/company?err=save_failed"
        return RedirectResponse(url=to, status_code=303)
    except Exception:
        return RedirectResponse(url="/settings/company?err=save_failed", status_code=303)
