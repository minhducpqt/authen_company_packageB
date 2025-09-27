# routers/project_payment_accounts.py
from __future__ import annotations

import os
import httpx
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, Form, Query, Path
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter()

async def _fetch_json(client: httpx.AsyncClient, url: str, access: Optional[str] = None):
    headers = {}
    if access:
        headers["Authorization"] = f"Bearer {access}"
    r = await client.get(url, headers=headers, timeout=20.0)
    r.raise_for_status()
    return r.json()

@router.get("/projects/payment-accounts", response_class=HTMLResponse)
async def page_projects_payment_accounts(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    access = get_access_token(request)
    me = await fetch_me(request)
    # Tải danh sách dự án (phụ thuộc company_scope từ cookie/token ở Service A)
    params = []
    if q: params.append(("q", q))
    if status: params.append(("status", status))
    qs = "&".join([f"{k}={v}" for k, v in params]) if params else ""
    url_projects = f"{API_BASE_URL}/api/v1/projects" + (f"?{qs}" if qs else "")

    async with httpx.AsyncClient() as client:
        projects_resp = await _fetch_json(client, url_projects, access)
        projects = projects_resp.get("data", [])

        # Tải danh sách tài khoản công ty (để render label & cho user chọn)
        url_cba = f"{API_BASE_URL}/api/v1/company_bank_accounts?size=200"
        cba_page = await _fetch_json(client, url_cba, access)
        company_accounts = cba_page.get("data", [])

        # Map id -> label
        def _label(cba: Dict[str, Any]) -> str:
            b = cba.get("bank") or {}
            parts = [
                (b.get("short_name") or b.get("name") or b.get("code") or "").strip(),
                cba.get("account_number") or "",
                cba.get("account_name") or "",
            ]
            return " — ".join([p for p in [parts[0], parts[1]] if p]) + (f" · {parts[2]}" if parts[2] else "")

        cba_options = [
            {"id": c["id"], "label": _label(c)}
            for c in company_accounts
        ]

        # Lấy summary payment-accounts cho từng dự án
        summaries: Dict[int, Dict[str, Any]] = {}
        for p in projects:
            pid = p["id"]
            url_summary = f"{API_BASE_URL}/api/v1/projects/{pid}/payment-accounts/summary"
            try:
                s = await _fetch_json(client, url_summary, access)
            except Exception:
                s = {"project_id": pid, "payment_accounts": {}, "cba_application_id": None, "cba_deposit_id": None}
            summaries[pid] = s

    return templates.TemplateResponse(
        "projects/payment_accounts_list.html",
        {
            "request": request,
            "me": me,
            "projects": projects,
            "summaries": summaries,
            "cba_options": cba_options,
            "q": q or "",
            "status": status or "",
        }
    )

@router.post("/projects/{project_id}/payment-accounts")
async def save_project_payment_accounts(
    request: Request,
    project_id: int = Path(..., ge=1),
    cba_application_id: Optional[int] = Form(None),
    cba_deposit_id: Optional[int] = Form(None),
):
    access = get_access_token(request)
    payload = {
        "cba_application_id": int(cba_application_id) if cba_application_id else None,
        "cba_deposit_id": int(cba_deposit_id) if cba_deposit_id else None,
    }

    async with httpx.AsyncClient() as client:
        r = await client.put(
            f"{API_BASE_URL}/api/v1/projects/{project_id}/payment-accounts",
            headers={"Authorization": f"Bearer {access}"},
            json=payload,
            timeout=20.0,
        )
        if r.status_code >= 400:
            msg = r.text.replace("\n", " ")[:400]
            return RedirectResponse(
                url=f"/projects/payment-accounts?status=ERR:{msg}",
                status_code=303
            )

    return RedirectResponse(url="/projects/payment-accounts", status_code=303)
