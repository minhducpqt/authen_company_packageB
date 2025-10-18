from __future__ import annotations
import os
import io
import httpx
from typing import List, Tuple, Dict, Any

from fastapi import APIRouter, UploadFile, Request, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token
from .registry import sniff_and_parse

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter(prefix="/giao-dich-ngan-hang/import", tags=["bank-import"])

# Helper
async def _api_get(client: httpx.AsyncClient, path: str, token: str, params: List[Tuple[str, str | int]] | None = None):
    return await client.get(
        f"{SERVICE_A_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        timeout=25.0,
    )

async def _api_post_json(client: httpx.AsyncClient, path: str, token: str, payload: Dict[str, Any], params: Dict[str, Any] | None = None):
    return await client.post(
        f"{SERVICE_A_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params=params or {},
        json=payload,
        timeout=45.0,
    )

@router.get("", response_class=HTMLResponse)
async def import_upload_form(request: Request, account_id: int | None = Query(None)):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fgiao-dich-ngan-hang%2Fimport", status_code=303)

    company_code = None
    async with httpx.AsyncClient() as client:
        r_me = await _api_get(client, "/auth/me", token)
    if r_me.status_code == 200:
        try:
            me = r_me.json()
            company_code = (me or {}).get("company_code")
        except Exception:
            pass

    accounts: list[dict] = []
    async with httpx.AsyncClient() as client:
        params_acc: list[tuple[str, str | int]] = [("status", True), ("page", 1), ("size", 200)]
        if company_code:
            params_acc.append(("company_code", company_code))
        r_acc = await _api_get(client, "/api/v1/company_bank_accounts", token, params_acc)
    if r_acc.status_code == 200:
        try:
            j = r_acc.json()
            accounts = j.get("data", [])
        except Exception:
            accounts = []

    return templates.TemplateResponse(
        "bank/import_upload.html",
        {
            "request": request,
            "title": "Import sao kê",
            "accounts": accounts,
            "prefill_account_id": account_id or "",
        },
    )

@router.post("/preview", response_class=HTMLResponse)
async def import_preview(request: Request, file: UploadFile, account_id: int = Form(...)):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fgiao-dich-ngan-hang%2Fimport", status_code=303)

    content = await file.read()

    result = sniff_and_parse(content, file.filename)
    if not result.get("ok"):
        return templates.TemplateResponse(
            "bank/import_preview.html",
            {
                "request": request,
                "title": "Preview sao kê",
                "error": "Không đọc được file hoặc không có parser phù hợp.",
                "result": {"rows": [], "row_errors": [], "errors": result.get("errors", [])},
                "filename": file.filename,
                "account_id": account_id,
            },
            status_code=400,
        )

    return templates.TemplateResponse(
        "bank/import_preview.html",
        {
            "request": request,
            "title": "Preview sao kê",
            "result": result,
            "filename": file.filename,
            "account_id": account_id,
        },
    )

@router.post("/apply", response_class=JSONResponse)
async def import_apply(request: Request):
    """
    Nhận:
      { "account_id": 123, "rows": [ ... ] }

    Gửi sang Service A theo schema BankBulkImportIn:
      {
        "company_code": "...",
        "policy": "STRICT" | "REPLACE",
        "items": [NormalizedTxnIn, ...]
      }
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # ---- Parse payload ----
    try:
        payload_in = await request.json()
    except Exception:
        return JSONResponse({"error": "bad_json"}, status_code=400)

    account_id = payload_in.get("account_id")
    rows = payload_in.get("rows") or []
    if not account_id or not isinstance(rows, list) or len(rows) == 0:
        return JSONResponse({"error": "invalid_payload"}, status_code=400)

    # ---- Lấy company_code từ /auth/me ----
    company_code = None
    async with httpx.AsyncClient() as client:
        r_me = await _api_get(client, "/auth/me", token)
    if r_me.status_code == 200:
        try:
            me = r_me.json()
            company_code = (me or {}).get("company_code")
        except Exception:
            pass
    if not company_code:
        return JSONResponse({"error": "no_company_code"}, status_code=400)

    # ---- Lấy thông tin tài khoản công ty ----
    async with httpx.AsyncClient() as client:
        r_acc = await _api_get(client, f"/api/v1/company_bank_accounts/{int(account_id)}", token)
    if r_acc.status_code != 200:
        return JSONResponse({"error": "account_not_found"}, status_code=400)

    try:
        account = r_acc.json()
    except Exception:
        account = None
    if not account:
        return JSONResponse({"error": "account_not_found"}, status_code=400)

    # Chuẩn hoá thông tin TK
    acc_number_raw = account.get("account_number") or account.get("account_no") or ""
    bank_code_raw = account.get("bank_code") or account.get("code") or ""
    acc_number = str(acc_number_raw).replace(" ", "").replace(".", "")
    bank_code = str(bank_code_raw).upper().strip()

    if not acc_number or not bank_code:
        return JSONResponse({
            "error": "account_missing_fields",
            "detail": {"bank_code": bank_code_raw, "account_number": acc_number_raw}
        }, status_code=400)

    if account.get("is_active") is False:
        return JSONResponse({"error": "account_inactive"}, status_code=400)

    # ---- Map rows -> items (NormalizedTxnIn) ----
    items: list[dict] = []
    for i, r in enumerate(rows, start=1):
        amt = float(r.get("amount") or 0)
        items.append({
            "bank_code": bank_code,
            "account_number": acc_number,
            "counter_account": r.get("counter_account") or None,
            "txn_time": r.get("txn_time"),      # ISO string
            "amount": amt,
            "currency": r.get("currency") or "VND",
            "description": r.get("description") or None,
            "ref_no": r.get("ref_no") or None,
            "provider_uid": r.get("provider_uid") or None,
            "statement_uid": r.get("statement_uid") or None,
            "src_line": i,
        })

    body = {
        "company_code": company_code,
        "policy": "STRICT",  # hoặc "REPLACE" nếu bạn muốn cho phép cập nhật trùng
        "items": items,
    }
    params = {"body_company_code": company_code}

    # ---- Gọi API Service A ----
    async with httpx.AsyncClient() as client:
        r = await _api_post_json(client, "/api/v1/bank-transactions/bulk", token, body, params)

    # ---- In log chi tiết để debug ----
    print("=== [DEBUG] ServiceA bulk result ===")
    print("Status:", r.status_code)
    try:
        print("Body:", r.json())
    except Exception:
        print("Text:", r.text[:400])

    # ---- Trả về frontend ----
    try:
        j = r.json()
    except Exception:
        j = {"detail": r.text[:400]}

    if r.status_code >= 400:
        return JSONResponse({
            "error": "upstream",
            "status": r.status_code,
            "body": j
        }, status_code=502)

    return JSONResponse(j, status_code=200)

async def import_apply(request: Request):
    """
    Nhận:
      { "account_id": 123, "rows": [ ... ] }

    Gửi sang Service A theo schema BankBulkImportIn:
      {
        "company_code": "...",
        "policy": "STRICT" | "REPLACE",
        "items": [NormalizedTxnIn, ...]
      }
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        payload_in = await request.json()
    except Exception:
        return JSONResponse({"error": "bad_json"}, status_code=400)

    account_id = payload_in.get("account_id")
    rows = payload_in.get("rows") or []
    if not account_id or not isinstance(rows, list) or len(rows) == 0:
        return JSONResponse({"error": "invalid_payload"}, status_code=400)

    # Lấy company_code
    company_code = None
    async with httpx.AsyncClient() as client:
        r_me = await _api_get(client, "/auth/me", token)
    if r_me.status_code == 200:
        try:
            me = r_me.json()
            company_code = (me or {}).get("company_code")
        except Exception:
            pass
    if not company_code:
        return JSONResponse({"error": "no_company_code"}, status_code=400)

    # Lấy thông tin tài khoản công ty để có account_number/bank_code
    account = None
    async with httpx.AsyncClient() as client:
        r_acc = await _api_get(client, f"/api/v1/company_bank_accounts/{int(account_id)}", token)
    if r_acc.status_code == 200:
        try:
            account = r_acc.json()
        except Exception:
            account = None
    if not account or not account.get("account_number"):
        return JSONResponse({"error": "account_not_found"}, status_code=400)

    acc_number = account["account_number"]
    acc_bank_code = account.get("bank_code")

    # Map rows -> items (NormalizedTxnIn)
    items: list[dict] = []
    for i, r in enumerate(rows, start=1):
        items.append({
            "bank_code"     : r.get("bank_code") or acc_bank_code,
            "account_number": acc_number,
            "counter_account": r.get("counter_account") or None,
            "txn_time"      : r.get("txn_time"),            # ISO string
            "amount"        : float(r.get("amount") or 0),  # bắt buộc
            "currency"      : r.get("currency") or "VND",
            "description"   : r.get("description") or None,
            "ref_no"        : r.get("ref_no") or None,
            "provider_uid"  : r.get("provider_uid") or None,
            "statement_uid" : r.get("statement_uid") or None,
            "src_line"      : i,
        })

    body = {
        "company_code": company_code,
        "policy": "STRICT",
        "items": items,
    }
    params = {"body_company_code": company_code}

    async with httpx.AsyncClient() as client:
        r = await _api_post_json(client, "/api/v1/bank-transactions/bulk", token, body, params)

    # trả kết quả
    try:
        j = r.json()
    except Exception:
        j = {"detail": r.text[:400]}

    if r.status_code >= 400:
        return JSONResponse({"error": "upstream", "status": r.status_code, "body": j}, status_code=502)

    return JSONResponse(j, status_code=200)
