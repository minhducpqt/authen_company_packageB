from __future__ import annotations
import os
from typing import Optional
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/settings/bank-accounts", tags=["settings:bank_accounts"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# --- helpers ---------------------------------------------------------------
async def _get_json(client: httpx.AsyncClient, url: str, headers: dict):
    r = await client.get(url, headers=headers)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None

async def _post_json(client: httpx.AsyncClient, url: str, headers: dict, payload: dict | None):
    r = await client.post(url, headers=headers, json=payload or {})
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

async def _delete(client: httpx.AsyncClient, url: str, headers: dict):
    r = await client.delete(url, headers=headers)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


# --- Endpoints -------------------------------------------------------------

@router.get("", response_class=HTMLResponse)
async def list_accounts(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    """
    Danh sách tài khoản NH của công ty đang đăng nhập.
    Dùng Service A:
      - GET /api/v1/company_bank_accounts?company_code=...&q=...&page=...&size=...
      - GET /api/v1/catalogs/banks  (để render tên ngân hàng)
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote('/settings/bank-accounts')}", status_code=303)

    company_code = me.get("company_code")
    if not company_code:
        return RedirectResponse(url="/account?err=no_company_code", status_code=303)

    params = {"company_code": company_code, "page": page, "size": size}
    if q:
        params["q"] = q
    page_data = {"data": [], "page": page, "size": size, "total": 0}
    banks = []
    load_err = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            # banks (để map code -> name)
            st_b, data_b = await _get_json(client, "/api/v1/catalogs/banks?page=1&size=500", {"Authorization": f"Bearer {token}"})
            if st_b == 200 and isinstance(data_b, dict):
                banks = data_b.get("data", data_b) or []
            # list CBA
            st, data = await _get_json(client, f"/api/v1/company_bank_accounts?{urlencode(params)}", {"Authorization": f"Bearer {token}"})
            if st == 200 and isinstance(data, dict):
                page_data = {
                    "data": data.get("data", []),
                    "page": data.get("page", page),
                    "size": data.get("size", size),
                    "total": data.get("total", 0),
                }
            else:
                load_err = f"Không tải được danh sách tài khoản (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    # map bank_code -> bank_name
    bank_name_map = { (b.get("code") or "").upper(): (b.get("name") or b.get("short_name") or b.get("code")) for b in (banks or []) }

    return templates.TemplateResponse(
        "pages/settings/bank_accounts/list.html",
        {
            "request": request,
            "title": "Thiết lập / Tài khoản ngân hàng",
            "me": me,
            "filters": {"q": q or ""},
            "page": page_data,
            "bank_name_map": bank_name_map,
            "load_err": load_err,
        },
    )


@router.get("/create", response_class=HTMLResponse)
async def create_form(request: Request):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/settings/bank-accounts/create", status_code=303)

    banks = []
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            st_b, data_b = await _get_json(
                client,
                "/api/v1/catalogs/banks?page=1&size=500",
                {"Authorization": f"Bearer {token}"}
            )
            if st_b == 200:
                # data_b có thể là dict {"data":[...], ...} hoặc list [...]. Ép thành list an toàn:
                if isinstance(data_b, dict):
                    banks = data_b.get("data") or []
                elif isinstance(data_b, list):
                    banks = data_b
    except Exception:
        banks = []

    return templates.TemplateResponse(
        "pages/settings/bank_accounts/edit.html",
        {"request": request, "title": "Thêm tài khoản ngân hàng", "me": me,
         "banks": banks, "mode": "create", "item": None}
    )


@router.post("/create")
async def create_submit(
    request: Request,
    bank_code: str = Form(...),
    account_number: str = Form(...),
    account_name: str = Form(""),
    is_active: str = Form("true"),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/settings/bank-accounts/create", status_code=303)

    company_code = me.get("company_code") or ""
    payload = {
        "company_code": company_code,
        "bank_code": (bank_code or "").strip(),
        "account_number": (account_number or "").strip(),
        "account_name": (account_name or "").strip() or None,
        "is_active": (is_active or "true").lower() == "true",
    }

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
        st, _ = await _post_json(client, "/api/v1/company_bank_accounts", {"Authorization": f"Bearer {token}"}, payload)

    to = "/settings/bank-accounts?msg=created" if st == 200 else "/settings/bank-accounts?err=create_failed"
    return RedirectResponse(url=to, status_code=303)


@router.get("/{cba_id}/edit", response_class=HTMLResponse)
async def edit_form(request: Request, cba_id: int):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote(f'/settings/bank-accounts/{cba_id}/edit')}", status_code=303)

    banks = []
    item = None
    load_err = None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            st_b, data_b = await _get_json(client, "/api/v1/catalogs/banks?page=1&size=500", {"Authorization": f"Bearer {token}"})
            if st_b == 200 and isinstance(data_b, dict):
                banks = data_b.get("data", data_b) or []

            st, data = await _get_json(client, f"/api/v1/company_bank_accounts/{cba_id}", {"Authorization": f"Bearer {token}"})
            if st == 200 and isinstance(data, dict):
                item = data
            else:
                load_err = f"Không tải được tài khoản (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/settings/bank_accounts/edit.html",
        {
            "request": request,
            "title": "Sửa tài khoản ngân hàng",
            "me": me,
            "banks": banks,
            "mode": "edit",
            "item": item,
            "load_err": load_err,
        },
    )


@router.post("/{cba_id}/edit")
async def edit_submit(
    request: Request,
    cba_id: int,
    bank_code: str = Form(...),
    account_number: str = Form(...),
    account_name: str = Form(""),
    is_active: str = Form("true"),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url=f"/login?next={quote(f'/settings/bank-accounts/{cba_id}/edit')}", status_code=303)

    payload = {
        "bank_code": (bank_code or "").strip(),
        "account_number": (account_number or "").strip(),
        "account_name": (account_name or "").strip() or None,
        "is_active": (is_active or "true").lower() == "true",
    }

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
        st, _ = await _put_json(client, f"/api/v1/company_bank_accounts/{cba_id}", {"Authorization": f"Bearer {token}"}, payload)

    to = "/settings/bank-accounts?msg=updated" if st == 200 else "/settings/bank-accounts?err=update_failed"
    return RedirectResponse(url=to, status_code=303)


@router.post("/{cba_id}/delete")
async def delete_submit(request: Request, cba_id: int):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=/settings/bank-accounts", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _delete(client, f"/api/v1/company_bank_accounts/{cba_id}", {"Authorization": f"Bearer {token}"})

    to = "/settings/bank-accounts?msg=deleted" if st == 200 else "/settings/bank-accounts?err=delete_failed"
    return RedirectResponse(url=to, status_code=303)
