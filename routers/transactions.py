# routers/transactions.py
from __future__ import annotations
import os
from typing import Optional, List, Tuple

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


# =========================================================
# 2.1 MUA HỒ SƠ — PAGE + DATA
# =========================================================
@router.get("/transactions/dossiers", response_class=HTMLResponse)
async def dossiers_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Ftransactions%2Fdossiers", status_code=303)

    return templates.TemplateResponse(
        "pages/transactions/dossiers.html",
        {
            "request": request,
            "title": "2.1 Mua hồ sơ",
            "init_q": q or "",
            "init_page": page,
            "init_size": size,
            "init_project_code": project_code or "",
        },
    )


@router.get("/transactions/dossiers/data", response_class=JSONResponse)
async def dossiers_data(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if q:
        params.append(("q", q))
    if project_code:
        params.append(("project_code", project_code))

    async with httpx.AsyncClient() as client:
        # GỌI ĐÚNG API BÊN A
        r = await _api_get(client, "/api/v1/overview/applications", token, params)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=200)


# =========================================================
# 2.2 ĐẶT CỌC — PAGE + DATA
# =========================================================
@router.get("/transactions/deposits", response_class=HTMLResponse)
async def deposits_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Ftransactions%2Fdeposits", status_code=303)

    return templates.TemplateResponse(
        "pages/transactions/deposits.html",
        {
            "request": request,
            "title": "2.2 Đặt cọc",
            "init_q": q or "",
            "init_page": page,
            "init_size": size,
            "init_project_code": project_code or "",
        },
    )


@router.get("/transactions/deposits/data", response_class=JSONResponse)
async def deposits_data(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if q:
        params.append(("q", q))
    if project_code:
        params.append(("project_code", project_code))

    async with httpx.AsyncClient() as client:
        # GỌI ĐÚNG API BÊN A
        r = await _api_get(client, "/api/v1/overview/deposits", token, params)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=200)


# =========================================================
# 2.3 TỔNG HỢP — PAGE + DATA
# =========================================================
@router.get("/transactions/summary", response_class=HTMLResponse)
async def summary_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Ftransactions%2Fsummary", status_code=303)

    return templates.TemplateResponse(
        "pages/transactions/summary.html",
        {
            "request": request,
            "title": "2.3 Tổng hợp",
            "init_q": q or "",
            "init_page": page,
            "init_size": size,
            "init_project_code": project_code or "",
        },
    )


@router.get("/transactions/summary/data", response_class=JSONResponse)
async def summary_data(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if q:
        params.append(("q", q))
    if project_code:
        params.append(("project_code", project_code))

    async with httpx.AsyncClient() as client:
        # GỌI ĐÚNG API BÊN A
        r = await _api_get(client, "/api/v1/overview/summary", token, params)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=200)


# =========================================================
# DETAIL: Toàn bộ orders của 1 khách (pending + paid)
# (phục vụ popup/detail ở cả 3 màn)
# =========================================================
@router.get("/transactions/customers/{customer_id}/orders", response_class=JSONResponse)
async def customer_orders_detail(
    request: Request,
    customer_id: int = Path(..., ge=1),
    project_code: Optional[str] = Query(None),
    type: Optional[str] = Query(None),  # APPLICATION | DEPOSIT | None
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = []
    if project_code:
        params.append(("project_code", project_code))
    if type:
        params.append(("type", type))

    async with httpx.AsyncClient() as client:
        # GỌI ĐÚNG API BÊN A
        r = await _api_get(
            client,
            f"/api/v1/overview/customers/{customer_id}/orders",
            token,
            params,
        )

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code == 404:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=200)
