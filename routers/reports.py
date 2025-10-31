# routers/reports.py
from __future__ import annotations
import os
from typing import Optional, Dict, Any, List, Tuple

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["reports"])
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# ---------- helpers ----------
async def _get_json(path: str, token: str, params: Dict[str, Any] | List[Tuple[str, Any]] | None = None):
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as c:
        r = await c.get(path, headers={"Authorization": f"Bearer {token}"}, params=params or {})
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"detail": r.text[:500]}

def _unauth():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


# ---------- 5.0 Tổng quan ----------
@router.get("/reports", response_class=HTMLResponse)
async def reports_home(request: Request):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports", status_code=303)
    return templates.TemplateResponse(
        "reports/index.html",
        {"request": request, "title": "Báo cáo thống kê"},
    )


# ---------- 5.1 Lô & điều kiện ----------
@router.get("/reports/lots/eligible", response_class=HTMLResponse)
async def lots_eligible_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Feligible", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project_code: params["project_code"] = project_code
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/lots/eligible", token, params)
    return templates.TemplateResponse(
        "reports/lots_eligible.html",
        {
            "request": request, "title": "Lô đủ điều kiện",
            "data": data if st == 200 else {"error": data},
            "project_code": project_code or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )

@router.get("/reports/lots/ineligible", response_class=HTMLResponse)
async def lots_ineligible_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Fineligible", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project_code: params["project_code"] = project_code
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/lots/ineligible", token, params)
    return templates.TemplateResponse(
        "reports/lots_ineligible.html",
        {
            "request": request, "title": "Lô KHÔNG đủ điều kiện",
            "data": data if st == 200 else {"error": data},
            "project_code": project_code or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )


# ---------- 5.2 Khách hàng & điều kiện ----------
@router.get("/reports/customers/eligible-lots", response_class=HTMLResponse)
async def customers_eligible_lots_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Feligible-lots", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project_code: params["project_code"] = project_code
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/customers/eligible", token, params)
    return templates.TemplateResponse(
        "reports/customers_eligible.html",
        {
            "request": request, "title": "Khách hàng đủ điều kiện & các lô liên quan",
            "data": data if st == 200 else {"error": data},
            "project_code": project_code or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )

@router.get("/reports/customers/ineligible-lots", response_class=HTMLResponse)
async def customers_ineligible_lots_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Fineligible-lots", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project_code: params["project_code"] = project_code
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/customers/ineligible", token, params)
    return templates.TemplateResponse(
        "reports/customers_ineligible.html",
        {
            "request": request, "title": "Khách hàng KHÔNG đủ điều kiện & các lô liên quan",
            "data": data if st == 200 else {"error": data},
            "project_code": project_code or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )


# ---------- 5.3 Mua hồ sơ (chi tiết/tổng hợp) ----------
@router.get("/reports/dossiers/paid/detail", response_class=HTMLResponse)
async def dossiers_paid_detail_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fdetail", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project_code: params["project_code"] = project_code
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/dossiers/paid/detail", token, params)
    return templates.TemplateResponse(
        "reports/dossiers_paid.html",
        {
            "request": request, "title": "Mua hồ sơ — chi tiết",
            "mode": "detail",
            "data": data if st == 200 else {"error": data},
            "project_code": project_code or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )

@router.get("/reports/dossiers/paid/summary", response_class=HTMLResponse)
async def dossiers_paid_summary_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fsummary", status_code=303)
    params: Dict[str, Any] = {}
    if project_code: params["project_code"] = project_code
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/dossiers/paid/summary", token, params)
    return templates.TemplateResponse(
        "reports/dossiers_paid.html",
        {
            "request": request, "title": "Mua hồ sơ — tổng hợp",
            "mode": "summary",
            "data": data if st == 200 else {"error": data},
            "project_code": project_code or "",
            "q": q or "",
        },
        status_code=200 if st == 200 else 502,
    )


# ---------- JSON endpoints (nếu cần load động từ FE) ----------
@router.get("/api/reports/{kind}", response_class=JSONResponse)
async def reports_api(
    request: Request,
    kind: str,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    map_path = {
        "lots_eligible": "/api/v1/reports/lots/eligible",
        "lots_ineligible": "/api/v1/reports/lots/ineligible",
        "customers_eligible": "/api/v1/reports/customers/eligible",
        "customers_ineligible": "/api/v1/reports/customers/ineligible",
        "dossiers_paid_detail": "/api/v1/reports/dossiers/paid/detail",
        "dossiers_paid_summary": "/api/v1/reports/dossiers/paid/summary",
    }
    path = map_path.get(kind)
    if not path:
        return JSONResponse({"error": "invalid_kind"}, status_code=400)

    params: Dict[str, Any] = {"page": page, "size": size}
    if project_code: params["project_code"] = project_code
    if q: params["q"] = q

    st, data = await _get_json(path, token, params)
    if st == 401:
        return _unauth()
    if st != 200:
        return JSONResponse({"error": "service_a_failed", "status": st, "body": data}, status_code=502)
    return JSONResponse(data, status_code=200)
