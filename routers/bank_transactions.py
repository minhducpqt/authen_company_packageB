# routers/bank_transactions.py
from __future__ import annotations
import os
from typing import Optional, List, Tuple, Dict, Any

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse

from utils.templates import templates
from utils.auth import get_access_token

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter()

# -----------------------
# Internal HTTP helpers
# -----------------------
async def _api_get(
    client: httpx.AsyncClient,
    path: str,
    token: str,
    params: List[Tuple[str, str | int]] | None = None,
):
    return await client.get(
        f"{SERVICE_A_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        timeout=25.0,
    )


# ============================
# 1) PAGE: /giao-dich-ngan-hang
# ============================
@router.get("/giao-dich-ngan-hang", response_class=HTMLResponse)
async def bank_transactions_page(
    request: Request,
    # bộ lọc
    account_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="free text: mô tả / số TK đối ứng / provider_uid / statement_uid"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[str] = Query("ALL"),
    sort: str = Query("-txn_time"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    token = get_access_token(request)
    print(f"[BANK] INFO ENTER PAGE token_present={bool(token)} path={request.url.path}")
    if not token:
        # Để middleware chuyển hướng; trả template login ở đây sẽ sai flow.
        return HTMLResponse("Redirecting...", status_code=303, headers={"Location": f"/login?next=%2Fgiao-dich-ngan-hang"})

    # 1) Xác thực nhanh qua /auth/me để biết company_code
    company_code = None
    async with httpx.AsyncClient() as client:
        r_me = await _api_get(client, "/auth/me", token)
        print(f"[BANK] INFO /auth/me -> {r_me.status_code}")
        if r_me.status_code == 200:
            try:
                me = r_me.json()
                company_code = (me or {}).get("company_code")
            except Exception:
                company_code = None

    # 2) Lấy danh sách tài khoản ngân hàng của công ty
    accounts: list[dict] = []
    async with httpx.AsyncClient() as client:
        params_acc: List[Tuple[str, str | int]] = [("status", True), ("page", 1), ("size", 200)]
        if company_code:
            params_acc.append(("company_code", company_code))
        r_acc = await _api_get(client, "/api/v1/company_bank_accounts", token, params_acc)
        print(f"[BANK] INFO GET /company_bank_accounts -> {r_acc.status_code}")
        if r_acc.status_code == 200:
            try:
                j = r_acc.json()
                accounts = j.get("data", []) if isinstance(j, dict) else []
            except Exception:
                accounts = []

    # 3) Gọi danh sách giao dịch
    page_data = {"data": [], "total": 0, "page": page, "size": size}
    try:
        # Build params
        params: Dict[str, str | int] = {
            "page": page,
            "size": size,
            "sort": sort,
        }
        # luôn ưu tiên lọc theo company_code nếu có
        if company_code:
            params["company_code"] = company_code

        # chỉ giữ tài khoản; ko có input ngân hàng.
        if account_id:
            params["account_id"] = int(account_id)
            # Tự nội suy bank_code (nếu API Service A dùng — không bắt buộc)
            acc = next((a for a in accounts if int(a.get("id", 0)) == int(account_id)), None)
            if acc and acc.get("bank_code"):
                params["bank_code"] = acc["bank_code"]

        if q:
            params["q"] = q
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if status and status != "ALL":
            params["status"] = status

        async with httpx.AsyncClient() as client:
            r_txn = await _api_get(client, "/api/v1/bank-transactions", token, list(params.items()))
        print(f"[BANK] INFO GET /bank-transactions params={params} -> {r_txn.status_code}")

        if r_txn.status_code == 200 and isinstance(r_txn.json(), dict):
            j = r_txn.json()
            page_data = {
                "data": j.get("data", []),
                "total": j.get("total", 0),
                "page": j.get("page", page),
                "size": j.get("size", size),
            }
    except Exception as e:
        print("[BANK] ERROR list txn:", e)

    # 4) Render
    resp = templates.TemplateResponse(
        "bank/transactions.html",
        {
            "request": request,
            "title": "Giao dịch ngân hàng",
            # UI data
            "accounts": accounts,
            "filters": {
                "account_id": account_id or "",
                "q": q or "",
                "date_from": date_from or "",
                "date_to": date_to or "",
                "status": status or "ALL",
                "sort": sort or "-txn_time",
            },
            "page": page_data,
        },
    )
    return resp


# ============================
# 2) DATA JSON (nếu cần AJAX)
# ============================
@router.get("/giao-dich-ngan-hang/data", response_class=JSONResponse)
async def bank_txn_data(
    request: Request,
    account_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[str] = Query("ALL"),
    sort: str = Query("-txn_time"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # company_code
    async with httpx.AsyncClient() as client:
        r_me = await _api_get(client, "/auth/me", token)
    if r_me.status_code != 200:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    company_code = (r_me.json() or {}).get("company_code")

    # lấy accounts để suy ra bank_code nếu cần
    accounts: list[dict] = []
    async with httpx.AsyncClient() as client:
        r_acc = await _api_get(
            client,
            "/api/v1/company_bank_accounts",
            token,
            [("status", True), ("page", 1), ("size", 200), ("company_code", company_code or "")],
        )
    if r_acc.status_code == 200:
        try:
            j = r_acc.json()
            accounts = j.get("data", [])
        except Exception:
            accounts = []

    params: Dict[str, str | int] = {
        "page": page,
        "size": size,
        "sort": sort,
    }
    if company_code:
        params["company_code"] = company_code
    if account_id:
        params["account_id"] = int(account_id)
        acc = next((a for a in accounts if int(a.get("id", 0)) == int(account_id)), None)
        if acc and acc.get("bank_code"):
            params["bank_code"] = acc["bank_code"]
    if q:
        params["q"] = q
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    if status and status != "ALL":
        params["status"] = status

    async with httpx.AsyncClient() as client:
        r_txn = await _api_get(client, "/api/v1/bank-transactions", token, list(params.items()))

    if r_txn.status_code >= 400:
        return JSONResponse({"error": "upstream", "status": r_txn.status_code}, status_code=502)
    return JSONResponse(r_txn.json(), status_code=200)