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

# -----------------------
# Small util
# -----------------------
def _to_int_or_none(v: Optional[str]) -> Optional[int]:
    """Chuẩn hoá: '' hoặc None -> None; số hợp lệ -> int."""
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        return int(s)
    except Exception:
        return None

def _match_to_bool(matched_str: Optional[str]) -> Optional[bool]:
    """
    Map UI matched filter:
      - 'MATCHED'   -> True
      - 'UNMATCHED' -> False
      - 'ALL'/None  -> None
    """
    if not matched_str or matched_str.upper() == "ALL":
        return None
    s = matched_str.upper()
    if s == "MATCHED":
        return True
    if s == "UNMATCHED":
        return False
    return None

# ============================================================
# 1) PAGE: /giao-dich-ngan-hang — danh sách giao dịch (HTML)
# ============================================================
@router.get("/giao-dich-ngan-hang", response_class=HTMLResponse)
async def bank_transactions_page(
    request: Request,
    account_id: Optional[str] = Query(None),  # nhận string để không 422 khi account_id=
    q: Optional[str] = Query(None, description="free text: mô tả / số TK đối ứng / provider_uid / statement_uid"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[str] = Query("ALL"),
    matched: Optional[str] = Query("ALL", description="ALL|MATCHED|UNMATCHED"),  # NEW
    no_ref_only: Optional[bool] = Query(False),  # NEW
    sort: str = Query("-txn_time"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),   # <-- mặc định 50
):
    token = get_access_token(request)
    print(f"[BANK] INFO ENTER PAGE token_present={bool(token)} path={request.url.path}")
    if not token:
        return HTMLResponse(
            "Redirecting...",
            status_code=303,
            headers={"Location": "/login?next=%2Fgiao-dich-ngan-hang"},
        )

    # 1) Lấy company_code
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

    # 2) Lấy danh sách tài khoản công ty
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

    # 3) Gọi danh sách giao dịch (SSR)
    account_id_int = _to_int_or_none(account_id)
    page_data = {"data": [], "total": 0, "page": page, "size": size}

    try:
        params: Dict[str, str | int] = {"page": page, "size": size, "sort": sort}
        if company_code:
            params["company_code"] = company_code

        # Map account_id -> bank_code + account_number (Service A dùng cặp này)
        if account_id_int is not None:
            selected = next((a for a in accounts if int(a.get("id", -1)) == account_id_int), None)
            if selected:
                if selected.get("bank_code"):
                    params["bank_code"] = selected["bank_code"]
                if selected.get("account_number"):
                    params["account_number"] = selected["account_number"]

        if q:
            params["q"] = q
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if status and status != "ALL":
            params["status"] = status

        # NEW: matched filter
        matched_bool = _match_to_bool(matched)
        if matched_bool is not None:
            params["matched"] = str(matched_bool).lower()

        # NEW: no_ref_only filter
        if bool(no_ref_only):
            params["no_ref_only"] = "true"

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

    # 4) Render template
    return templates.TemplateResponse(
        "bank/transactions.html",
        {
            "request": request,
            "title": "Giao dịch ngân hàng",
            "accounts": accounts,
            "filters": {
                "account_id": account_id or "",
                "q": q or "",
                "date_from": date_from or "",
                "date_to": date_to or "",
                "status": status or "ALL",
                "matched": matched or "ALL",
                "no_ref_only": bool(no_ref_only),
                "sort": sort or "-txn_time",
            },
            "page": page_data,
        },
    )

# ============================================================
# 2) DATA JSON (AJAX) — cùng API Service A
# ============================================================
@router.get("/giao-dich-ngan-hang/data", response_class=JSONResponse)
async def bank_txn_data(
    request: Request,
    account_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[str] = Query("ALL"),
    matched: Optional[str] = Query("ALL"),         # NEW
    no_ref_only: Optional[bool] = Query(False),    # NEW
    sort: str = Query("-txn_time"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),   # <-- mặc định 50
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # 1) company_code
    async with httpx.AsyncClient() as client:
        r_me = await _api_get(client, "/auth/me", token)
    if r_me.status_code != 200:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    company_code = (r_me.json() or {}).get("company_code")

    # 1.1) Lấy danh sách CBA để map account_id -> bank_code/account_number
    accounts: list[dict] = []
    async with httpx.AsyncClient() as client:
        params_acc: List[Tuple[str, str | int]] = [("status", True), ("page", 1), ("size", 200)]
        if company_code:
            params_acc.append(("company_code", company_code))
        r_acc = await _api_get(client, "/api/v1/company_bank_accounts", token, params_acc)
        if r_acc.status_code == 200:
            try:
                j = r_acc.json()
                accounts = j.get("data", []) if isinstance(j, dict) else []
            except Exception:
                accounts = []

    # 2) gọi Service A
    account_id_int = _to_int_or_none(account_id)
    params: Dict[str, str | int] = {"page": page, "size": size, "sort": sort}
    if company_code:
        params["company_code"] = company_code

    if account_id_int is not None:
        selected = next((a for a in accounts if int(a.get("id", -1)) == account_id_int), None)
        if selected:
            if selected.get("bank_code"):
                params["bank_code"] = selected["bank_code"]
            if selected.get("account_number"):
                params["account_number"] = selected["account_number"]

    if q:
        params["q"] = q
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    if status and status != "ALL":
        params["status"] = status

    # NEW: matched filter
    matched_bool = _match_to_bool(matched)
    if matched_bool is not None:
        params["matched"] = str(matched_bool).lower()

    # NEW: no_ref_only
    if bool(no_ref_only):
        params["no_ref_only"] = "true"

    async with httpx.AsyncClient() as client:
        r_txn = await _api_get(client, "/api/v1/bank-transactions", token, list(params.items()))

    if r_txn.status_code >= 400:
        return JSONResponse({"error": "upstream", "status": r_txn.status_code}, status_code=502)
    return JSONResponse(r_txn.json(), status_code=200)
