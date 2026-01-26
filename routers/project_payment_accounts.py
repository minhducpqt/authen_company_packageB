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

# IMPORTANT: dùng prefix cố định để tránh đè /projects/{project_id}
router = APIRouter(prefix="/projects/payment-accounts")

async def _fetch_json(client: httpx.AsyncClient, url: str, access: Optional[str] = None):
    headers = {}
    if access:
        headers["Authorization"] = f"Bearer {access}"
    r = await client.get(url, headers=headers, timeout=20.0)
    r.raise_for_status()
    return r.json()

@router.get("", response_class=HTMLResponse)
async def page_projects_payment_accounts(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    access = get_access_token(request)
    me = await fetch_me(request)

    params = []
    if q: params.append(("q", q))
    if status: params.append(("status", status))
    qs = "&".join([f"{k}={v}" for k, v in params]) if params else ""
    url_projects = f"{API_BASE_URL}/api/v1/projects" + (f"?{qs}" if qs else "")

    async with httpx.AsyncClient() as client:
        # 1) Projects
        projects_resp = await _fetch_json(client, url_projects, access)
        projects = projects_resp.get("data", [])

        # 2) Company Bank Accounts (để render label & chọn)
        url_cba = f"{API_BASE_URL}/api/v1/company_bank_accounts?size=200&status=true"
        cba_page = await _fetch_json(client, url_cba, access)
        company_accounts = cba_page.get("data", [])

        # Build options + map
        def _label(cba: Dict[str, Any]) -> str:
            b = cba.get("bank") or {}
            name = (b.get("short_name") or b.get("name") or b.get("code") or "").strip()
            acc_no = (cba.get("account_number") or "").strip()
            acc_name = (cba.get("account_name") or "").strip()
            base = " — ".join([p for p in [name, acc_no] if p])
            return base + (f" · {acc_name}" if acc_name else "")

        cba_options = [{"id": c["id"], "label": _label(c)} for c in company_accounts]

        # id -> {short_name, account_number}
        cba_map: Dict[int, Dict[str, str]] = {}
        for c in company_accounts:
            b = c.get("bank") or {}
            cba_map[c["id"]] = {
                "short_name": (b.get("short_name") or b.get("name") or b.get("code") or "").strip(),
                "account_number": (c.get("account_number") or "").strip(),
            }

        # 3) Summaries cho từng project
        summaries: Dict[int, Dict[str, Any]] = {}
        # 4) Freeze status cho từng project
        freeze_map: Dict[int, Dict[str, Any]] = {}

        for p in projects:
            pid = p["id"]
            url_summary = f"{API_BASE_URL}/api/v1/projects/{pid}/payment-accounts/summary"
            url_freeze = f"{API_BASE_URL}/api/v1/projects/{pid}/payment-accounts/freeze-status"
            try:
                s = await _fetch_json(client, url_summary, access)
            except Exception:
                s = {"project_id": pid, "payment_accounts": {}, "cba_application_id": None, "cba_deposit_id": None}
            summaries[pid] = s

            try:
                fz = await _fetch_json(client, url_freeze, access)
                freeze_map[pid] = {
                    "frozen": bool(fz.get("frozen", False)),
                    "frozen_at": fz.get("frozen_at"),
                    "reason": fz.get("reason"),
                }
            except Exception:
                freeze_map[pid] = {"frozen": False, "frozen_at": None, "reason": None}

    return templates.TemplateResponse(
        "projects/payment_accounts_list.html",
        {
            "request": request,
            "me": me,
            "projects": projects,
            "summaries": summaries,
            "freeze_map": freeze_map,     # <-- dùng trong template để hiện badge/disable
            "cba_options": cba_options,
            "cba_map": cba_map,           # <-- thêm map để hiển thị đẹp
            "q": q or "",
            "status": status or "",
            "title": "Cấu hình nhận tiền",
        }
    )

@router.post("/{project_id}")
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
            msg = ""
            try:
                j = r.json()
                msg = (j.get("detail") or j.get("message") or "").strip()
            except Exception:
                msg = ""
            if not msg:
                msg = r.text.replace("\n", " ").strip()
            msg = msg[:400]
            return RedirectResponse(
                url=f"/projects/payment-accounts?status=ERR:{msg}",
                status_code=303
            )

    return RedirectResponse(url="/projects/payment-accounts?status=OK:SAVED", status_code=303)

# NEW: nút “Đóng băng” từ UI (không có gỡ)
@router.post("/{project_id}/freeze")
async def freeze_project_payment_accounts_ui(
    request: Request,
    project_id: int = Path(..., ge=1),
    reason: Optional[str] = Form(None),
):
    access = get_access_token(request)
    # reason là tùy chọn; đẩy lên query cho đơn giản (API A nhận qua query)
    qs = f"?reason={reason}" if reason else ""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{API_BASE_URL}/api/v1/projects/{project_id}/payment-accounts/freeze{qs}",
            headers={"Authorization": f"Bearer {access}"},
            timeout=20.0,
        )
        if r.status_code >= 400:
            msg = r.text.replace("\n", " ")[:400]
            return RedirectResponse(
                url=f"/projects/payment-accounts?status=ERR:{msg}",
                status_code=303
            )
    return RedirectResponse(url="/projects/payment-accounts?status=OK:FROZEN", status_code=303)
