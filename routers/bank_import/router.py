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
    """Form upload: có thể nhận sẵn account_id từ trang list."""
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fgiao-dich-ngan-hang%2Fimport", status_code=303)

    # fetch me -> company_code
    company_code = None
    async with httpx.AsyncClient() as client:
        r_me = await _api_get(client, "/auth/me", token)
    if r_me.status_code == 200:
        try:
            me = r_me.json()
            company_code = (me or {}).get("company_code")
        except Exception:
            pass

    # Danh sách tài khoản công ty để user chọn (nếu chưa truyền)
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
    """
    Upload file -> parse -> hiện preview.
    account_id: bắt buộc (đã xác định TK công ty).
    """
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fgiao-dich-ngan-hang%2Fimport", status_code=303)

    content = await file.read()

    # detect & parse
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

    # Lưu tạm rows để apply (client gửi lại JSON)
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
    Client gửi JSON: {
      "account_id": 123,
      "rows": [ ... chuẩn hóa ... ]
    }
    -> Forward sang Service A:
       POST /api/v1/bank-transactions/bulk?body_company_code=...
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "bad_json"}, status_code=400)

    account_id = payload.get("account_id")
    rows = payload.get("rows") or []
    if not account_id or not isinstance(rows, list) or len(rows) == 0:
        return JSONResponse({"error": "invalid_payload"}, status_code=400)

    # fetch company_code
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

    # body gửi sang Service A
    body = {
        "account_id": int(account_id),
        "rows": rows,
    }
    params = {"body_company_code": company_code}

    async with httpx.AsyncClient() as client:
        r = await _api_post_json(client, "/api/v1/bank-transactions/bulk", token, body, params)

    # Trả kết quả về UI
    try:
        j = r.json()
    except Exception:
        j = {"detail": r.text[:400]}

    if r.status_code >= 400:
        return JSONResponse({"error": "upstream", "status": r.status_code, "body": j}, status_code=502)

    return JSONResponse(j, status_code=200)
