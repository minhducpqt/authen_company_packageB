# routers/transactions.py
from __future__ import annotations
import os
from typing import Optional, List, Tuple, Dict, Any

import httpx
from fastapi import APIRouter, Request, Query
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


# =========================================================
# 2.1 — MUA HỒ SƠ (list page + data)
# =========================================================
@router.get("/transactions/dossiers", response_class=HTMLResponse)
async def dossiers_page(
    request: Request,
    q: Optional[str] = Query(None),
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=100),   # tối đa 100 khách/trang
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Ftransactions%2Fdossiers", status_code=303)

    return templates.TemplateResponse(
        "transactions/dossiers.html",
        {
            "request": request,
            "title": "2.1 Mua hồ sơ",
            "init_q": q or "",
            "init_project_code": project_code or "",
            "init_page": page,
            "init_size": size,
        },
    )


@router.get("/transactions/dossiers/data", response_class=JSONResponse)
async def dossiers_data(
    request: Request,
    q: Optional[str] = Query(None, description="Họ tên/CCCD/SDT (không dấu được hỗ trợ ở Service A)"),
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=100),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [
        ("page", page),
        ("size", size),
    ]
    if q:
        params.append(("q", q))
    if project_code:
        params.append(("project_code", project_code))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/admin/overview/dossiers", token, params)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=200)


# =========================================================
# 2.2 — ĐẶT CỌC (list page + data)
# =========================================================
@router.get("/transactions/deposits", response_class=HTMLResponse)
async def deposits_page(
    request: Request,
    q: Optional[str] = Query(None),
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=100),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Ftransactions%2Fdeposits", status_code=303)

    return templates.TemplateResponse(
        "transactions/deposits.html",
        {
            "request": request,
            "title": "2.2 Đặt cọc",
            "init_q": q or "",
            "init_project_code": project_code or "",
            "init_page": page,
            "init_size": size,
        },
    )


@router.get("/transactions/deposits/data", response_class=JSONResponse)
async def deposits_data(
    request: Request,
    q: Optional[str] = Query(None),
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=100),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [
        ("page", page),
        ("size", size),
    ]
    if q:
        params.append(("q", q))
    if project_code:
        params.append(("project_code", project_code))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/admin/overview/deposits", token, params)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=200)


# =========================================================
# 2.3 — TỔNG HỢP (list page + data)
# =========================================================
@router.get("/transactions/summary", response_class=HTMLResponse)
async def summary_page(
    request: Request,
    q: Optional[str] = Query(None),
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=100),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Ftransactions%2Fsummary", status_code=303)

    return templates.TemplateResponse(
        "transactions/summary.html",
        {
            "request": request,
            "title": "2.3 Tổng hợp",
            "init_q": q or "",
            "init_project_code": project_code or "",
            "init_page": page,
            "init_size": size,
        },
    )


@router.get("/transactions/summary/data", response_class=JSONResponse)
async def summary_data(
    request: Request,
    q: Optional[str] = Query(None),
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=100),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [
        ("page", page),
        ("size", size),
    ]
    if q:
        params.append(("q", q))
    if project_code:
        params.append(("project_code", project_code))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/admin/overview/summary", token, params)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=200)
