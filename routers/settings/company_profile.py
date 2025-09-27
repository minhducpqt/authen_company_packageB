# routers/settings/company_profile.py
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
async def company_form(request: Request):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote('/settings/company')}", status_code=303)

    company = {}
    load_err = None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            st, data = await _get_json(client, "/api/v1/company/profile", {"Authorization": f"Bearer {token}"})
            if st == 200 and isinstance(data, dict):
                company = data
            else:
                load_err = f"Không tải được thông tin công ty (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/settings/company_profile.html",
        {"request": request, "title": "Thiết lập / Thông tin công ty", "me": me,
         "company": company, "load_err": load_err}
    )

@router.post("", response_class=HTMLResponse)
async def company_save(
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
        return RedirectResponse(url=f"/login?next={quote('/settings/company')}", status_code=303)

    payload = {
        "name": name.strip() or None,
        "tax_code": tax_code.strip() or None,
        "email": email.strip() or None,
        "phone": phone.strip() or None,
        "address": address.strip() or None,
        "logo_url": logo_url.strip() or None,
    }

    ok = False
    err = None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            st, _ = await _put_json(client, "/api/v1/company/profile",
                                    {"Authorization": f"Bearer {token}"}, payload)
            ok = (st == 200)
            if not ok:
                err = f"Lưu thất bại (HTTP {st})."
    except Exception as e:
        err = str(e)

    to = "/settings/company?msg=saved" if ok else f"/settings/company?err={quote(err or 'save_failed')}"
    return RedirectResponse(url=to, status_code=303)
