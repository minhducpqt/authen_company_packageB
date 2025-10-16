# routers/customers.py
from __future__ import annotations
import os
from typing import Optional, List, Tuple, Dict, Any

import httpx
from fastapi import APIRouter, Request, Query, Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8824")

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
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        timeout=20.0,
    )


async def _api_put_json(
    client: httpx.AsyncClient, path: str, token: str, payload: Dict[str, Any]
):
    return await client.put(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=20.0,
    )


# ======================================
# LIST PAGE (khung HTML) + DATA (JSON)
# ======================================
@router.get("/customers", response_class=HTMLResponse)
async def customers_page(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=200),  # default 50 cho mượt
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fcustomers", status_code=303)

    return templates.TemplateResponse(
        "customers/interactive.html",
        {
            "request": request,
            "title": "Khách hàng",
            "init_q": q or "",
            "init_page": page,
            "init_size": size,
        },
    )


@router.get("/customers/data", response_class=JSONResponse)
async def customers_data(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if q:
        params.append(("q", q))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/customers", token, params)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=200)


# ==========================
# DETAIL PAGE (view + edit)
# ==========================
@router.get("/customers/{customer_id}", response_class=HTMLResponse)
async def customer_detail_page(
    request: Request,
    customer_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url=f"/login?next=%2Fcustomers%2F{customer_id}", status_code=303
        )

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, f"/api/v1/customers/{customer_id}", token)

    if r.status_code == 401:
        return RedirectResponse(
            url=f"/login?next=%2Fcustomers%2F{customer_id}", status_code=303
        )
    if r.status_code == 404:
        return templates.TemplateResponse(
            "errors/simple.html",
            {
                "request": request,
                "title": "Không tìm thấy",
                "message": "Khách hàng không tồn tại.",
            },
            status_code=404,
        )
    if r.status_code >= 500:
        return templates.TemplateResponse(
            "errors/simple.html",
            {
                "request": request,
                "title": "Lỗi",
                "message": f"Tải dữ liệu lỗi ({r.status_code}).",
            },
            status_code=502,
        )

    return templates.TemplateResponse(
        "customers/detail.html",
        {
            "request": request,
            "title": f"Khách hàng #{customer_id}",
            "customer": r.json(),
        },
    )


# ===========================================
# SAVE (PUT JSON proxy -> Service A /customers)
# Accepts JSON; if client gửi form thì tự chuyển
# ===========================================
@router.put("/customers/{customer_id}", response_class=JSONResponse)
async def customer_detail_save(
    request: Request,
    customer_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # Try read JSON; fallback form
    payload: Dict[str, Any]
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        form = await request.form()
        payload = {
            "full_name": (form.get("full_name") or "").strip() or None,
            "cccd": (form.get("cccd") or "").strip() or None,
            "address": (form.get("address") or "").strip() or None,
            "phone": (form.get("phone") or "").strip() or None,
            "email": (form.get("email") or "").strip() or None,
        }

    # Forward to Service A
    async with httpx.AsyncClient() as client:
        r = await _api_put_json(
            client, f"/api/v1/customers/{customer_id}", token, payload
        )

    # Map a few common cases for UI
    if r.status_code == 409:
        # Trùng CCCD
        msg = "CCCD đã tồn tại trong hệ thống."
        try:
            msg = r.json().get("detail", msg)
        except Exception:
            pass
        return JSONResponse({"error": "conflict", "field": "cccd", "detail": msg}, status_code=409)

    if r.status_code >= 400:
        # Trả nguyên thân để UI hiển thị
        try:
            body = r.json()
        except Exception:
            body = {"detail": r.text[:400]}
        return JSONResponse(body, status_code=r.status_code)

    return JSONResponse(r.json(), status_code=200)
