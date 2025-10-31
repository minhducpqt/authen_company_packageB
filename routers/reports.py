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


# ---------- logging helper ----------
def _log(msg: str):
    print(f"[REPORTS_B] {msg}")

def _preview_body(data: Any, limit: int = 300) -> str:
    try:
        import json
        s = json.dumps(data, ensure_ascii=False)
    except Exception:
        s = str(data)
    if len(s) > limit:
        return s[:limit] + "...(truncated)"
    return s


# ---------- HTTP helpers (auto log) ----------
async def _get_json(
    path: str,
    token: str,
    params: Dict[str, Any] | List[Tuple[str, Any]] | None = None,
):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ GET {url} params={params or {}} headers.keys={list(headers.keys())}")

    async with httpx.AsyncClient(timeout=30.0) as c:
        try:
            r = await c.get(url, headers=headers, params=params or {})
        except Exception as e:
            _log(f"← EXC {url} error={e}")
            return 599, {"detail": str(e)}

    try:
        js = r.json()
        _log(f"← {r.status_code} {url} json={_preview_body(js)}")
        return r.status_code, js
    except Exception:
        text_preview = (r.text or "")[:300]
        _log(f"← {r.status_code} {url} text={text_preview}")
        return r.status_code, {"detail": r.text[:500]}


def _unauth():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


# ---------- 5.0 Tổng quan ----------
@router.get("/reports", response_class=HTMLResponse)
async def reports_home(request: Request):
    _log(f"REQ /reports url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports", status_code=303)
    return templates.TemplateResponse(
        "reports/index.html",
        {"request": request, "title": "Báo cáo thống kê"},
    )


# ---------- 5.1 Lô & điều kiện ----------
@router.get("/reports/lots/eligible", response_class=HTMLResponse)
async def lots_eligible_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
):
    _log(f"REQ /reports/lots/eligible url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Feligible", status_code=303)

    # Service A endpoint: /api/v1/reports/lot-deposits/eligible?project=...
    params: Dict[str, Any] = {"page": page, "size": size}
    if project:
        params["project"] = project

    st, data = await _get_json("/api/v1/reports/lot-deposits/eligible", token, params)
    ctx = {
        "request": request,
        "title": "Lô đủ điều kiện",
        "data": data if st == 200 else {"error": data},
        "project": project or "",
        "page": page,
        "size": size,
    }
    return templates.TemplateResponse("reports/lots_eligible.html", ctx, status_code=200 if st == 200 else 502)


@router.get("/reports/lots/ineligible", response_class=HTMLResponse)
async def lots_ineligible_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
):
    _log(f"REQ /reports/lots/ineligible url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Fineligible", status_code=303)

    # Service A endpoint: /api/v1/reports/lot-deposits/not-eligible?project=...
    params: Dict[str, Any] = {"page": page, "size": size}
    if project:
        params["project"] = project

    st, data = await _get_json("/api/v1/reports/lot-deposits/not-eligible", token, params)
    ctx = {
        "request": request,
        "title": "Lô KHÔNG đủ điều kiện",
        "data": data if st == 200 else {"error": data},
        "project": project or "",
        "page": page,
        "size": size,
    }
    return templates.TemplateResponse("reports/lots_ineligible.html", ctx, status_code=200 if st == 200 else 502)


# ---------- 5.2 Khách hàng & điều kiện ----------
@router.get("/reports/customers/eligible-lots", response_class=HTMLResponse)
async def customers_eligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
):
    _log(f"REQ /reports/customers/eligible-lots url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Feligible-lots", status_code=303)

    # Service A endpoint: /api/v1/reports/customers/eligible-lots?project=...
    params: Dict[str, Any] = {"page": page, "size": size}
    if project:
        params["project"] = project

    st, data = await _get_json("/api/v1/reports/customers/eligible-lots", token, params)
    ctx = {
        "request": request,
        "title": "Khách hàng đủ điều kiện & các lô liên quan",
        "data": data if st == 200 else {"error": data},
        "project": project or "",
        "page": page,
        "size": size,
    }
    return templates.TemplateResponse("reports/customers_eligible.html", ctx, status_code=200 if st == 200 else 502)


@router.get("/reports/customers/not-eligible-lots", response_class=HTMLResponse)
async def customers_ineligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
):
    _log(f"REQ /reports/customers/not-eligible-lots url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Fineligible-lots", status_code=303)

    # Service A endpoint: /api/v1/reports/customers/not-eligible-lots?project=...
    params: Dict[str, Any] = {"page": page, "size": size}
    if project:
        params["project"] = project

    st, data = await _get_json("/api/v1/reports/customers/not-eligible-lots", token, params)
    ctx = {
        "request": request,
        "title": "Khách hàng KHÔNG đủ điều kiện & các lô liên quan",
        "data": data if st == 200 else {"error": data},
        "project": project or "",
        "page": page,
        "size": size,
    }
    return templates.TemplateResponse("reports/customers_ineligible.html", ctx, status_code=200 if st == 200 else 502)


# ---------- 5.3 Mua hồ sơ (chi tiết/tổng hợp) ----------
@router.get("/reports/dossiers/paid/detail", response_class=HTMLResponse)
async def dossiers_paid_detail_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
):
    _log(f"REQ /reports/dossiers/paid/detail url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fdetail", status_code=303)

    # Service A endpoint: /api/v1/reports/dossiers/paid/detail?project=...
    params: Dict[str, Any] = {"page": page, "size": size}
    if project:
        params["project"] = project

    st, data = await _get_json("/api/v1/reports/dossiers/paid/detail", token, params)
    ctx = {
        "request": request,
        "title": "Mua hồ sơ — chi tiết",
        "mode": "detail",
        "data": data if st == 200 else {"error": data},
        "project": project or "",
        "page": page,
        "size": size,
    }
    return templates.TemplateResponse("reports/dossiers_paid.html", ctx, status_code=200 if st == 200 else 502)


@router.get("/reports/dossiers/paid/summary", response_class=HTMLResponse)
async def dossiers_paid_summary_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
):
    _log(f"REQ /reports/dossiers/paid/summary url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fsummary", status_code=303)

    # Service A endpoint (theo code của bạn): summary by customer và totals-by-type
    # Ở FE dùng chung template; nếu cần tách riêng 2 tab thì gọi 2 API khác nhau.
    params: Dict[str, Any] = {}
    if project:
        params["project"] = project

    # Gọi 2 API để render cùng trang (nếu bạn chỉ cần 1 trong 2, bỏ cái còn lại)
    st1, data1 = await _get_json("/api/v1/reports/dossiers/paid/summary-customer", token, params)
    st2, data2 = await _get_json("/api/v1/reports/dossiers/paid/totals-by-type", token, params)

    data = {
        "summary_customer": data1 if st1 == 200 else {"error": data1, "status": st1},
        "totals_by_type":  data2 if st2 == 200 else {"error": data2, "status": st2},
    }
    ok = (st1 == 200) or (st2 == 200)
    ctx = {
        "request": request,
        "title": "Mua hồ sơ — tổng hợp",
        "mode": "summary",
        "data": data,
        "project": project or "",
    }
    return templates.TemplateResponse("reports/dossiers_paid.html", ctx, status_code=200 if ok else 502)


# ---------- JSON proxy (nếu FE cần load động) ----------
@router.get("/api/reports/{kind}", response_class=JSONResponse)
async def reports_api(
    request: Request,
    kind: str,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=1000),
):
    _log(f"REQ /api/reports/{kind} url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → 401 JSON")
        return _unauth()

    # Map sang endpoint mới bên A (đã dùng param 'project')
    map_path = {
        "lots_eligible":              "/api/v1/reports/lot-deposits/eligible",
        "lots_ineligible":            "/api/v1/reports/lot-deposits/not-eligible",
        "customers_eligible":         "/api/v1/reports/customers/eligible-lots",
        "customers_ineligible":       "/api/v1/reports/customers/not-eligible-lots",
        "dossiers_paid_detail":       "/api/v1/reports/dossiers/paid/detail",
        "dossiers_paid_summary_cust": "/api/v1/reports/dossiers/paid/summary-customer",
        "dossiers_paid_totals_type":  "/api/v1/reports/dossiers/paid/totals-by-type",
    }
    path = map_path.get(kind)
    if not path:
        _log(f"ERR invalid kind={kind}")
        return JSONResponse({"error": "invalid_kind"}, status_code=400)

    params: Dict[str, Any] = {"page": page, "size": size}
    if project:
        params["project"] = project

    st, data = await _get_json(path, token, params)
    if st == 401:
        _log("AUTH 401 from Service A")
        return _unauth()
    if st != 200:
        _log(f"UPSTREAM non-200 status={st} body={_preview_body(data)}")
        return JSONResponse({"error": "service_a_failed", "status": st, "body": data}, status_code=502)
    return JSONResponse(data, status_code=200)
