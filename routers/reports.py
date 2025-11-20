# routers/reports.py
from __future__ import annotations
import os
from typing import Optional, Dict, Any, List, Tuple

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

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


async def _proxy_export(
    path: str,
    token: str,
    params: Dict[str, Any],
    fallback_filename: str,
) -> Response:
    """
    Gọi Service A để nhận file (xlsx) và stream về cho browser.
    """
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ EXPORT {url} params={params}")
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.get(url, headers=headers, params=params)

    content_type = r.headers.get(
        "content-type",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    disposition = r.headers.get(
        "content-disposition",
        f'attachment; filename="{fallback_filename}"',
    )
    _log(f"← EXPORT {url} status={r.status_code} len={len(r.content)}")
    return Response(
        content=r.content,
        status_code=r.status_code,
        media_type=content_type,
        headers={"Content-Disposition": disposition},
    )


def _unauth():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


# ---------- Helper: load ACTIVE projects & chọn dự án ----------
async def _load_projects(token: str, project_param: Optional[str]) -> tuple[list[dict], str]:
    """
    Gọi Service A /api/v1/projects để lấy danh sách dự án ACTIVE.
    - Nếu project_param có giá trị -> dùng luôn (upper & strip).
    - Nếu không có, và chỉ có 1 dự án ACTIVE -> auto chọn dự án đó.
    - Trả về (projects, selected_project_code)
    """
    st, pj = await _get_json(
        "/api/v1/projects",
        token,
        {"status": "ACTIVE", "size": 1000},
    )
    projects: list[dict] = []
    selected = (project_param or "").strip().upper()

    if st == 200 and isinstance(pj, dict):
        projects = pj.get("data") or pj.get("items") or []
        _log(f"_load_projects: got {len(projects)} active projects")
        if not selected and len(projects) == 1:
            selected = (projects[0].get("project_code") or "").upper()
            _log(f"_load_projects: auto-selected single project={selected}")
    else:
        _log(f"_load_projects: failed to load projects status={st} body={pj}")

    return projects, selected


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


# ============================================================
# 5.1 LÔ & ĐIỀU KIỆN  (VIEW /view/project-*)
# ============================================================

@router.get("/reports/lots/eligible", response_class=HTMLResponse)
async def lots_eligible_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    lot_prefix: Optional[str] = Query(None, description="Prefix mã lô, ví dụ: CL03"),
    limit: Optional[int] = Query(500, ge=1, le=5000, description="Giới hạn số dòng tối đa"),
    export: Optional[str] = Query(None, description="xlsx để export"),
):
    """
    Lô đủ điều kiện (≥ 2 khách đặt tiền).
    Gọi Service A: /api/v1/reports/view/project-lots-eligible
    """
    _log(f"REQ /reports/lots/eligible url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Feligible", status_code=303)

    projects, selected_project = await _load_projects(token, project)

    # Export XLSX
    if export == "xlsx" and selected_project:
        params: Dict[str, Any] = {"project": selected_project, "format": "xlsx"}
        if lot_prefix:
            params["lot_code"] = lot_prefix
        if limit is not None:
            params["limit"] = limit
        filename = f"project_lots_eligible_{selected_project}.xlsx"
        return await _proxy_export(
            "/api/v1/reports/view/project-lots-eligible",
            token,
            params,
            filename,
        )

    # View HTML
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None
    if selected_project:
        params = {"project": selected_project}
        if lot_prefix:
            params["lot_code"] = lot_prefix
        if limit is not None:
            params["limit"] = limit

        st, js = await _get_json("/api/v1/reports/view/project-lots-eligible", token, params)
        if st == 200:
            data = js
        else:
            error = {"status": st, "body": js}

    ctx = {
        "request": request,
        "title": "Lô đủ điều kiện",
        "projects": projects,
        "project": selected_project,
        "lot_prefix": lot_prefix or "",
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/lots_eligible.html", ctx)


@router.get("/reports/lots/ineligible", response_class=HTMLResponse)
async def lots_ineligible_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    lot_prefix: Optional[str] = Query(None, description="Prefix mã lô, ví dụ: CL03"),
    limit: Optional[int] = Query(500, ge=1, le=5000, description="Giới hạn số dòng tối đa"),
    export: Optional[str] = Query(None, description="xlsx để export"),
):
    """
    Lô KHÔNG đủ điều kiện (0–1 khách).
    Gọi Service A: /api/v1/reports/view/project-lots-not-eligible
    """
    _log(f"REQ /reports/lots/ineligible url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Fineligible", status_code=303)

    projects, selected_project = await _load_projects(token, project)

    # Export
    if export == "xlsx" and selected_project:
        params: Dict[str, Any] = {"project": selected_project, "format": "xlsx"}
        if lot_prefix:
            params["lot_code"] = lot_prefix
        if limit is not None:
            params["limit"] = limit
        filename = f"project_lots_not_eligible_{selected_project}.xlsx"
        return await _proxy_export(
            "/api/v1/reports/view/project-lots-not-eligible",
            token,
            params,
            filename,
        )

    # View
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None
    if selected_project:
        params = {"project": selected_project}
        if lot_prefix:
            params["lot_code"] = lot_prefix
        if limit is not None:
            params["limit"] = limit

        st, js = await _get_json("/api/v1/reports/view/project-lots-not-eligible", token, params)
        if st == 200:
            data = js
        else:
            error = {"status": st, "body": js}

    ctx = {
        "request": request,
        "title": "Lô KHÔNG đủ điều kiện",
        "projects": projects,
        "project": selected_project,
        "lot_prefix": lot_prefix or "",
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/lots_ineligible.html", ctx)


# ============================================================
# 5.2 KHÁCH HÀNG & ĐIỀU KIỆN
# ============================================================

@router.get("/reports/customers/eligible-lots", response_class=HTMLResponse)
async def customers_eligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None, description="Lọc theo CCCD khách"),
    lot_prefix: Optional[str] = Query(None, description="Prefix mã lô"),
    limit: Optional[int] = Query(500, ge=1, le=5000),
    export: Optional[str] = Query(None, description="xlsx để export"),
):
    """
    Khách + lô đủ điều kiện.
    Gọi Service A: /api/v1/reports/view/project-customers-lots-eligible
    """
    _log(f"REQ /reports/customers/eligible-lots url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Feligible-lots", status_code=303)

    projects, selected_project = await _load_projects(token, project)

    # Export
    if export == "xlsx" and selected_project:
        params: Dict[str, Any] = {
            "project": selected_project,
            "expose_phone": "true",
            "format": "xlsx",
        }
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if lot_prefix:
            params["lot_code"] = lot_prefix
        if limit is not None:
            params["limit"] = limit

        filename = f"project_customers_lots_eligible_{selected_project}.xlsx"
        return await _proxy_export(
            "/api/v1/reports/view/project-customers-lots-eligible",
            token,
            params,
            filename,
        )

    # View
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    if selected_project:
        params = {
            "project": selected_project,
            "expose_phone": "true",
        }
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if lot_prefix:
            params["lot_code"] = lot_prefix
        if limit is not None:
            params["limit"] = limit

        st, js = await _get_json("/api/v1/reports/view/project-customers-lots-eligible", token, params)
        if st == 200:
            data = js
        else:
            error = {"status": st, "body": js}

    ctx = {
        "request": request,
        "title": "Khách hàng đủ điều kiện & các lô",
        "projects": projects,
        "project": selected_project,
        "customer_cccd": customer_cccd or "",
        "lot_prefix": lot_prefix or "",
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/customers_eligible.html", ctx)


@router.get("/reports/customers/not-eligible-lots", response_class=HTMLResponse)
async def customers_ineligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None, description="Lọc theo CCCD khách"),
    lot_prefix: Optional[str] = Query(None, description="Prefix mã lô"),
    limit: Optional[int] = Query(500, ge=1, le=5000),
    export: Optional[str] = Query(None, description="xlsx để export"),
):
    """
    Khách + lô KHÔNG đủ điều kiện.
    Gọi Service A: /api/v1/reports/view/project-customers-lots-not-enough
    """
    _log(f"REQ /reports/customers/not-eligible-lots url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Fineligible-lots", status_code=303)

    projects, selected_project = await _load_projects(token, project)

    # Export
    if export == "xlsx" and selected_project:
        params: Dict[str, Any] = {
            "project": selected_project,
            "expose_phone": "true",
            "format": "xlsx",
        }
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if lot_prefix:
            params["lot_code"] = lot_prefix
        if limit is not None:
            params["limit"] = limit

        filename = f"project_customers_lots_not_enough_{selected_project}.xlsx"
        return await _proxy_export(
            "/api/v1/reports/view/project-customers-lots-not-enough",
            token,
            params,
            filename,
        )

    # View
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    if selected_project:
        params = {
            "project": selected_project,
            "expose_phone": "true",
        }
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if lot_prefix:
            params["lot_code"] = lot_prefix
        if limit is not None:
            params["limit"] = limit

        st, js = await _get_json("/api/v1/reports/view/project-customers-lots-not-enough", token, params)
        if st == 200:
            data = js
        else:
            error = {"status": st, "body": js}

    ctx = {
        "request": request,
        "title": "Khách hàng KHÔNG đủ điều kiện & các lô",
        "projects": projects,
        "project": selected_project,
        "customer_cccd": customer_cccd or "",
        "lot_prefix": lot_prefix or "",
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/customers_ineligible.html", ctx)


# ============================================================
# 5.3 MUA HỒ SƠ (chi tiết / tổng hợp)
# ============================================================

@router.get("/reports/dossiers/paid/detail", response_class=HTMLResponse)
async def dossiers_paid_detail_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None, description="Lọc theo CCCD khách"),
    limit: Optional[int] = Query(1000, ge=1, le=10000),
    export: Optional[str] = Query(None, description="xlsx để export"),
):
    """
    Chi tiết các đơn mua hồ sơ theo dự án.
    Gọi Service A: /api/v1/reports/view/project-dossier-items
    """
    _log(f"REQ /reports/dossiers/paid/detail url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fdetail", status_code=303)

    projects, selected_project = await _load_projects(token, project)

    # Export
    if export == "xlsx" and selected_project:
        params: Dict[str, Any] = {
            "project": selected_project,
            "expose_phone": "true",
            "format": "xlsx",
        }
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if limit is not None:
            params["limit"] = limit

        filename = f"dossier_detail_{selected_project}.xlsx"
        return await _proxy_export(
            "/api/v1/reports/view/project-dossier-items",
            token,
            params,
            filename,
        )

    # View
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    if selected_project:
        params = {
            "project": selected_project,
            "expose_phone": "true",
        }
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if limit is not None:
            params["limit"] = limit

        st, js = await _get_json("/api/v1/reports/view/project-dossier-items", token, params)
        if st == 200:
            data = js
        else:
            error = {"status": st, "body": js}

    ctx = {
        "request": request,
        "title": "Mua hồ sơ — chi tiết",
        "mode": "detail",
        "projects": projects,
        "project": selected_project,
        "customer_cccd": customer_cccd or "",
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/dossiers_paid.html", ctx)


@router.get("/reports/dossiers/paid/summary", response_class=HTMLResponse)
async def dossiers_paid_summary_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    export: Optional[str] = Query(None, description="summary_customer / totals_by_type để export"),
):
    """
    Tổng hợp mua hồ sơ:
    - v_dossier_paid_summary_customer
    - v_dossier_paid_totals_by_type
    (phần này vẫn dùng các API cũ của Service A)
    """
    _log(f"REQ /reports/dossiers/paid/summary url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fsummary", status_code=303)

    projects, selected_project = await _load_projects(token, project)

    params: Dict[str, Any] = {}
    if selected_project:
        params["project"] = selected_project

    # Export
    if export in ("summary_customer", "totals_by_type") and selected_project:
        exp_params = dict(params)
        exp_params["format"] = "xlsx"
        if export == "summary_customer":
            path = "/api/v1/reports/dossiers/paid/summary-customer"
            filename = f"dossier_summary_customer_{selected_project}.xlsx"
        else:
            path = "/api/v1/reports/dossiers/paid/totals-by-type"
            filename = f"dossier_totals_by_type_{selected_project}.xlsx"
        return await _proxy_export(path, token, exp_params, filename)

    # View
    st1, data1 = await _get_json("/api/v1/reports/dossiers/paid/summary-customer", token, params)
    st2, data2 = await _get_json("/api/v1/reports/dossiers/paid/totals-by-type", token, params)

    data = {
        "summary_customer": data1 if st1 == 200 else {"error": data1, "status": st1},
        "totals_by_type": data2 if st2 == 200 else {"error": data2, "status": st2},
    }
    ok = (st1 == 200) or (st2 == 200)

    ctx = {
        "request": request,
        "title": "Mua hồ sơ — tổng hợp",
        "mode": "summary",
        "projects": projects,
        "project": selected_project,
        "data": data,
    }
    return templates.TemplateResponse("reports/dossiers_paid.html", ctx, status_code=200 if ok else 502)


# ---------- JSON proxy cũ (nếu FE cần load động) ----------
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

    # Map sang endpoint bên A (cũ)
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
