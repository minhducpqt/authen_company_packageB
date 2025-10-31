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
            return r.status_code, {"detail": (r.text or "")[:500]}

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
    project: Optional[str] = Query(None, alias="project"),  # nhận ?project=...
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Feligible", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project: params["project"] = project  # ✅ A yêu cầu 'project'
    if q: params["q"] = q
    # ✅ Map đúng endpoint A
    st, data = await _get_json("/api/v1/reports/lot-deposits/eligible", token, params)
    return templates.TemplateResponse(
        "reports/lots_eligible.html",
        {
            "request": request, "title": "Lô đủ điều kiện",
            "data": data if st == 200 else {"error": data},
            "project_code": project or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )

@router.get("/reports/lots/ineligible", response_class=HTMLResponse)
async def lots_ineligible_page(
    request: Request,
    project: Optional[str] = Query(None, alias="project"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Fineligible", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project: params["project"] = project
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/lot-deposits/not-eligible", token, params)  # ✅ đúng path
    return templates.TemplateResponse(
        "reports/lots_ineligible.html",
        {
            "request": request, "title": "Lô KHÔNG đủ điều kiện",
            "data": data if st == 200 else {"error": data},
            "project_code": project or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )


# ---------- 5.1b Cọc lô (eligible / not-eligible) ----------
@router.get("/reports/lot-deposits/eligible", response_class=HTMLResponse)
async def lot_deposits_eligible_page(
    request: Request,
    project: Optional[str] = Query(None, alias="project"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Flot-deposits%2Feligible", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project: params["project"] = project
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/lot-deposits/eligible", token, params)
    return templates.TemplateResponse(
        "reports/lot_deposits_eligible.html",
        {
            "request": request, "title": "Cọc lô — đủ điều kiện",
            "data": data if st == 200 else {"error": data},
            "project_code": project or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )

@router.get("/reports/lot-deposits/not-eligible", response_class=HTMLResponse)
async def lot_deposits_not_eligible_page(
    request: Request,
    project: Optional[str] = Query(None, alias="project"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Flot-deposits%2Fnot-eligible", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project: params["project"] = project
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/lot-deposits/not-eligible", token, params)
    return templates.TemplateResponse(
        "reports/lot_deposits_ineligible.html",
        {
            "request": request, "title": "Cọc lô — KHÔNG đủ điều kiện",
            "data": data if st == 200 else {"error": data},
            "project_code": project or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )


# ---------- 5.2 Khách hàng & điều kiện ----------
@router.get("/reports/customers/eligible-lots", response_class=HTMLResponse)
async def customers_eligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, alias="project"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Feligible-lots", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project: params["project"] = project
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/customers/eligible-lots", token, params)  # ✅ đúng path
    return templates.TemplateResponse(
        "reports/customers_eligible.html",
        {
            "request": request, "title": "Khách hàng đủ điều kiện & các lô liên quan",
            "data": data if st == 200 else {"error": data},
            "project_code": project or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )

@router.get("/reports/customers/ineligible-lots", response_class=HTMLResponse)
async def customers_ineligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, alias="project"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Fineligible-lots", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project: params["project"] = project
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/customers/not-eligible-lots", token, params)  # ✅ đúng path
    return templates.TemplateResponse(
        "reports/customers_ineligible.html",
        {
            "request": request, "title": "Khách hàng KHÔNG đủ điều kiện & các lô liên quan",
            "data": data if st == 200 else {"error": data},
            "project_code": project or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )


# ---------- 5.3 Mua hồ sơ (chi tiết/tổng hợp) ----------
@router.get("/reports/dossiers/paid/detail", response_class=HTMLResponse)
async def dossiers_paid_detail_page(
    request: Request,
    project: Optional[str] = Query(None, alias="project"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fdetail", status_code=303)
    params: Dict[str, Any] = {"page": page, "size": size}
    if project: params["project"] = project
    if q: params["q"] = q
    st, data = await _get_json("/api/v1/reports/dossiers/paid/detail", token, params)
    return templates.TemplateResponse(
        "reports/dossiers_paid.html",
        {
            "request": request, "title": "Mua hồ sơ — chi tiết",
            "mode": "detail",
            "data": data if st == 200 else {"error": data},
            "project_code": project or "",
            "q": q or "",
            "page": page, "size": size,
        },
        status_code=200 if st == 200 else 502,
    )

@router.get("/reports/dossiers/paid/summary", response_class=HTMLResponse)
async def dossiers_paid_summary_page(
    request: Request,
    project: Optional[str] = Query(None, alias="project"),
    view: str = Query("customer", pattern="^(customer|type)$"),  # customer | type
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fsummary", status_code=303)
    params: Dict[str, Any] = {}
    if project: params["project"] = project
    # Map view -> path
    if view == "customer":
        path = "/api/v1/reports/dossiers/paid/summary-customer"
        mode = "summary_customer"
    else:
        path = "/api/v1/reports/dossiers/paid/totals-by-type"
        mode = "summary_type"

    st, data = await _get_json(path, token, params)
    return templates.TemplateResponse(
        "reports/dossiers_paid.html",
        {
            "request": request, "title": "Mua hồ sơ — tổng hợp",
            "mode": mode,
            "data": data if st == 200 else {"error": data},
            "project_code": project or "",
        },
        status_code=200 if st == 200 else 502,
    )


# ---------- JSON endpoints (load động nếu cần) ----------
@router.get("/api/reports/{kind}", response_class=JSONResponse)
async def reports_api(
    request: Request,
    kind: str,
    project: Optional[str] = Query(None, alias="project"),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    # ✅ Map đúng các path trên A
    map_path = {
        "lots_eligible": "/api/v1/reports/lot-deposits/eligible",
        "lots_ineligible": "/api/v1/reports/lot-deposits/not-eligible",
        "lot_deposits_eligible": "/api/v1/reports/lot-deposits/eligible",
        "lot_deposits_not_eligible": "/api/v1/reports/lot-deposits/not-eligible",
        "customers_eligible": "/api/v1/reports/customers/eligible-lots",
        "customers_ineligible": "/api/v1/reports/customers/not-eligible-lots",
        "dossiers_paid_detail": "/api/v1/reports/dossiers/paid/detail",
        "dossiers_paid_summary_customer": "/api/v1/reports/dossiers/paid/summary-customer",
        "dossiers_paid_totals_by_type": "/api/v1/reports/dossiers/paid/totals-by-type",
    }
    path = map_path.get(kind)
    if not path:
        return JSONResponse({"error": "invalid_kind"}, status_code=400)

    params: Dict[str, Any] = {"page": page, "size": size}
    if project: params["project"] = project  # ✅ đúng tên tham số A
    if q: params["q"] = q

    st, data = await _get_json(path, token, params)
    if st == 401:
        return _unauth()
    if st != 200:
        return JSONResponse({"error": "service_a_failed", "status": st, "body": data}, status_code=502)
    return JSONResponse(data, status_code=200)


# ---------- API cho toolbar: danh sách dự án ACTIVE (FE gọi) ----------
@router.get("/projects/options", response_class=JSONResponse)
async def project_options_for_reports(
    request: Request,
    size: int = Query(1000, ge=1, le=2000),
):
    """
    Dùng cho toolbar report (dropdown dự án).
    - Lấy company_code từ Service A: /auth/me
    - Gọi Service A: /api/v1/projects/public?company_code=...&status=ACTIVE
    - Trả về {options: [{project_code, name, status}]}
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # lấy company_code
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as c:
            me_r = await c.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        if me_r.status_code != 200:
            return JSONResponse({"error": "auth_me_failed", "status": me_r.status_code}, status_code=502)
        me = me_r.json() or {}
    except Exception as e:
        return JSONResponse({"error": "auth_me_exception", "msg": str(e)}, status_code=502)

    company_code = (me or {}).get("company_code")
    if not company_code:
        return JSONResponse({"error": "missing_company_code"}, status_code=400)

    params = {
        "company_code": company_code,
        "status": "ACTIVE",
        "page": 1,
        "size": size,
    }
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as c:
            r = await c.get("/api/v1/projects/public", params=params, headers={"Authorization": f"Bearer {token}"})
    except Exception as e:
        return JSONResponse({"error": "service_a_connect_fail", "msg": str(e)}, status_code=502)

    if r.status_code != 200:
        try:
            detail = r.json()
        except Exception:
            detail = (r.text or "")[:300]
        return JSONResponse({"error": "service_a_failed", "status": r.status_code, "detail": detail}, status_code=502)

    raw = r.json() or {}
    items = raw.get("data") or []
    options = []
    for x in items:
        code = (x or {}).get("project_code") or (x or {}).get("code")
        name = (x or {}).get("name") or code
        if code:
            options.append({"project_code": code, "name": name, "status": x.get("status")})
    return JSONResponse({"options": options}, status_code=200)
