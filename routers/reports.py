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
async def _get_raw(
    path: str,
    token: str,
    params: Dict[str, Any] | List[Tuple[str, Any]] | None = None,
):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ GET {url} params={params or {}} headers.keys={list(headers.keys())}")

    async with httpx.AsyncClient(timeout=60.0) as c:
        try:
            r = await c.get(url, headers=headers, params=params or {})
        except Exception as e:
            _log(f"← EXC {url} error={e}")
            # giả lập Response-like
            class Dummy:
                status_code = 599
                content = b""
                headers = {}
                text = str(e)

                def json(self):
                    raise ValueError("no json")

            return Dummy()
    _log(f"← {r.status_code} {url} (len={len(r.content)})")
    return r


async def _get_json(
    path: str,
    token: str,
    params: Dict[str, Any] | List[Tuple[str, Any]] | None = None,
):
    r = await _get_raw(path, token, params)
    try:
        js = r.json()
        _log(f"   json={_preview_body(js)}")
        return r.status_code, js
    except Exception:
        text_preview = (r.text or "")[:300]
        _log(f"   text={text_preview}")
        return r.status_code, {"detail": r.text[:500]}


def _unauth():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


# ---------- Helper: load list active projects ----------
async def _fetch_active_projects(token: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Gọi Service A lấy danh sách dự án ACTIVE của company hiện tại.
    Trả về (projects, default_project_code). Nếu chỉ có 1 dự án thì
    dùng project_code của nó làm mặc định.
    """
    # NOTE: path/param này dựa theo convention trước đây.
    # Nếu Service A dùng path khác (vd /api/v1/business/projects)
    # bạn chỉ cần chỉnh lại ở đây.
    st, data = await _get_json(
        "/api/v1/projects",
        token,
        {"status": "ACTIVE", "size": 1000},
    )
    projects: List[Dict[str, Any]] = []
    default_project: Optional[str] = None

    if st == 200 and isinstance(data, dict):
        projects = data.get("items") or data.get("projects") or []
        if len(projects) == 1:
            p0 = projects[0] or {}
            default_project = p0.get("project_code") or p0.get("code")
    else:
        _log(f"_fetch_active_projects: upstream status={st} body={_preview_body(data)}")

    return projects, default_project


# ======================================================
# 5.0 Tổng quan
# ======================================================
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


# ======================================================
# 5.1 Lô & điều kiện (sử dụng các VIEW /view/... bên Service A)
# ======================================================

@router.get("/reports/lots/eligible", response_class=HTMLResponse)
async def lots_eligible_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    lot_code: Optional[str] = Query(None, description="lọc mã lô (prefix, không phân biệt hoa thường)"),
    limit: Optional[int] = Query(500, ge=1, le=5000, description="Số dòng tối đa"),
    export: Optional[str] = Query(None, description="xlsx để xuất file"),
):
    """
    Màn 'Lô đủ điều kiện' (>= 2 khách đặt tiền trên cùng lô).
    Dùng VIEW: /api/v1/reports/view/project-lots-eligible
    """
    _log(f"REQ /reports/lots/eligible url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Feligible", status_code=303)

    projects, default_project = await _fetch_active_projects(token)
    effective_project = project or default_project

    data: Dict[str, Any]
    status = 200

    params: Dict[str, Any] = {}
    if effective_project:
        params["project"] = effective_project
        if lot_code:
            params["lot_code"] = lot_code
        if limit:
            params["limit"] = limit

        # export trực tiếp từ Service A
        if export == "xlsx":
            params["format"] = "xlsx"
            raw = await _get_raw("/api/v1/reports/view/project-lots-eligible", token, params)
            filename = f"lots_eligible_{effective_project}.xlsx"
            return Response(
                content=raw.content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                status_code=raw.status_code,
            )

        status, data = await _get_json(
            "/api/v1/reports/view/project-lots-eligible",
            token,
            params,
        )
        if status != 200:
            data = {"error": data, "status": status}
    else:
        # chưa chọn dự án
        data = {"items": [], "count": 0}

    ctx = {
        "request": request,
        "title": "Lô đủ điều kiện",
        "data": data,
        "projects": projects,
        "project": effective_project or "",
        "lot_code": lot_code or "",
        "limit": limit,
    }
    return templates.TemplateResponse(
        "reports/lots_eligible.html",
        ctx,
        status_code=200 if status == 200 else 502,
    )


@router.get("/reports/lots/ineligible", response_class=HTMLResponse)
async def lots_ineligible_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    lot_code: Optional[str] = Query(None, description="lọc mã lô (prefix)"),
    limit: Optional[int] = Query(500, ge=1, le=5000, description="Số dòng tối đa"),
    export: Optional[str] = Query(None, description="xlsx để xuất file"),
):
    """
    Màn 'Lô KHÔNG đủ điều kiện' (0–1 khách).
    Dùng VIEW: /api/v1/reports/view/project-lots-not-eligible
    """
    _log(f"REQ /reports/lots/ineligible url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Flots%2Fineligible", status_code=303)

    projects, default_project = await _fetch_active_projects(token)
    effective_project = project or default_project

    data: Dict[str, Any]
    status = 200

    params: Dict[str, Any] = {}
    if effective_project:
        params["project"] = effective_project
        if lot_code:
            params["lot_code"] = lot_code
        if limit:
            params["limit"] = limit

        if export == "xlsx":
            params["format"] = "xlsx"
            raw = await _get_raw("/api/v1/reports/view/project-lots-not-eligible", token, params)
            filename = f"lots_not_eligible_{effective_project}.xlsx"
            return Response(
                content=raw.content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                status_code=raw.status_code,
            )

        status, data = await _get_json(
            "/api/v1/reports/view/project-lots-not-eligible",
            token,
            params,
        )
        if status != 200:
            data = {"error": data, "status": status}
    else:
        data = {"items": [], "count": 0}

    ctx = {
        "request": request,
        "title": "Lô KHÔNG đủ điều kiện",
        "data": data,
        "projects": projects,
        "project": effective_project or "",
        "lot_code": lot_code or "",
        "limit": limit,
    }
    return templates.TemplateResponse(
        "reports/lots_ineligible.html",
        ctx,
        status_code=200 if status == 200 else 502,
    )


# ======================================================
# 5.2 Khách hàng & điều kiện (VIEW /view/project-customers-...)
# ======================================================

@router.get("/reports/customers/eligible-lots", response_class=HTMLResponse)
async def customers_eligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None, description="lọc CCCD khách (exact)"),
    lot_code: Optional[str] = Query(None, description="lọc mã lô (prefix)"),
    limit: Optional[int] = Query(500, ge=1, le=5000),
    export: Optional[str] = Query(None, description="xlsx để xuất file"),
):
    _log(f"REQ /reports/customers/eligible-lots url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Feligible-lots", status_code=303)

    projects, default_project = await _fetch_active_projects(token)
    effective_project = project or default_project

    data: Dict[str, Any]
    status = 200

    params: Dict[str, Any] = {}
    if effective_project:
        params["project"] = effective_project
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if lot_code:
            params["lot_code"] = lot_code
        if limit:
            params["limit"] = limit

        if export == "xlsx":
            params["format"] = "xlsx"
            raw = await _get_raw("/api/v1/reports/view/project-customers-lots-eligible", token, params)
            filename = f"customers_lots_eligible_{effective_project}.xlsx"
            return Response(
                content=raw.content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                status_code=raw.status_code,
            )

        status, data = await _get_json(
            "/api/v1/reports/view/project-customers-lots-eligible",
            token,
            params,
        )
        if status != 200:
            data = {"error": data, "status": status}
    else:
        data = {"items": [], "count": 0}

    ctx = {
        "request": request,
        "title": "Khách hàng đủ điều kiện & các lô",
        "data": data,
        "projects": projects,
        "project": effective_project or "",
        "customer_cccd": customer_cccd or "",
        "lot_code": lot_code or "",
        "limit": limit,
    }
    return templates.TemplateResponse(
        "reports/customers_eligible.html",
        ctx,
        status_code=200 if status == 200 else 502,
    )


@router.get("/reports/customers/not-eligible-lots", response_class=HTMLResponse)
async def customers_ineligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None, description="lọc CCCD khách (exact)"),
    lot_code: Optional[str] = Query(None, description="lọc mã lô (prefix)"),
    limit: Optional[int] = Query(500, ge=1, le=5000),
    export: Optional[str] = Query(None, description="xlsx để xuất file"),
):
    _log(f"REQ /reports/customers/not-eligible-lots url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fcustomers%2Fnot-eligible-lots", status_code=303)

    projects, default_project = await _fetch_active_projects(token)
    effective_project = project or default_project

    data: Dict[str, Any]
    status = 200

    params: Dict[str, Any] = {}
    if effective_project:
        params["project"] = effective_project
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if lot_code:
            params["lot_code"] = lot_code
        if limit:
            params["limit"] = limit

        if export == "xlsx":
            params["format"] = "xlsx"
            raw = await _get_raw("/api/v1/reports/view/project-customers-lots-not-enough", token, params)
            filename = f"customers_lots_not_enough_{effective_project}.xlsx"
            return Response(
                content=raw.content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                status_code=raw.status_code,
            )

        status, data = await _get_json(
            "/api/v1/reports/view/project-customers-lots-not-enough",
            token,
            params,
        )
        if status != 200:
            data = {"error": data, "status": status}
    else:
        data = {"items": [], "count": 0}

    ctx = {
        "request": request,
        "title": "Khách hàng KHÔNG đủ điều kiện & các lô",
        "data": data,
        "projects": projects,
        "project": effective_project or "",
        "customer_cccd": customer_cccd or "",
        "lot_code": lot_code or "",
        "limit": limit,
    }
    return templates.TemplateResponse(
        "reports/customers_ineligible.html",
        ctx,
        status_code=200 if status == 200 else 502,
    )


# ======================================================
# 5.3 Mua hồ sơ (chi tiết/tổng hợp)
#   - Chi tiết dùng VIEW v_report_project_customer_dossier_items
#   - Tổng hợp dùng các API cũ /dossiers/paid/*
# ======================================================

@router.get("/reports/dossiers/paid/detail", response_class=HTMLResponse)
async def dossiers_paid_detail_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None, description="lọc CCCD khách"),
    limit: Optional[int] = Query(500, ge=1, le=5000),
    export: Optional[str] = Query(None, description="xlsx để xuất file"),
):
    _log(f"REQ /reports/dossiers/paid/detail url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fdetail", status_code=303)

    projects, default_project = await _fetch_active_projects(token)
    effective_project = project or default_project

    data: Dict[str, Any]
    status = 200

    params: Dict[str, Any] = {}
    if effective_project:
        params["project"] = effective_project
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if limit:
            params["limit"] = limit

        if export == "xlsx":
            params["format"] = "xlsx"
            raw = await _get_raw("/api/v1/reports/view/project-dossier-items", token, params)
            filename = f"dossier_items_{effective_project}.xlsx"
            return Response(
                content=raw.content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
                status_code=raw.status_code,
            )

        status, data = await _get_json(
            "/api/v1/reports/view/project-dossier-items",
            token,
            params,
        )
        if status != 200:
            data = {"error": data, "status": status}
    else:
        data = {"items": [], "count": 0}

    ctx = {
        "request": request,
        "title": "Mua hồ sơ — chi tiết",
        "mode": "detail",
        "data": data,
        "projects": projects,
        "project": effective_project or "",
        "customer_cccd": customer_cccd or "",
        "limit": limit,
    }
    return templates.TemplateResponse(
        "reports/dossiers_paid.html",
        ctx,
        status_code=200 if status == 200 else 502,
    )


@router.get("/reports/dossiers/paid/summary", response_class=HTMLResponse)
async def dossiers_paid_summary_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
):
    _log(f"REQ /reports/dossiers/paid/summary url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fsummary", status_code=303)

    projects, default_project = await _fetch_active_projects(token)
    effective_project = project or default_project

    params: Dict[str, Any] = {}
    if effective_project:
        params["project"] = effective_project

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
        "data": data,
        "projects": projects,
        "project": effective_project or "",
    }
    return templates.TemplateResponse(
        "reports/dossiers_paid.html",
        ctx,
        status_code=200 if ok else 502,
    )


# ======================================================
# JSON proxy (nếu FE cần load động)
# ======================================================
@router.get("/api/reports/{kind}", response_class=JSONResponse)
async def reports_api(
    request: Request,
    kind: str,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    limit: Optional[int] = Query(500, ge=1, le=5000),
):
    _log(f"REQ /api/reports/{kind} url={request.url}")
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → 401 JSON")
        return _unauth()

    map_path = {
        "lots_eligible": "/api/v1/reports/view/project-lots-eligible",
        "lots_ineligible": "/api/v1/reports/view/project-lots-not-eligible",
        "customers_eligible": "/api/v1/reports/view/project-customers-lots-eligible",
        "customers_not_enough": "/api/v1/reports/view/project-customers-lots-not-enough",
        "dossiers_items": "/api/v1/reports/view/project-dossier-items",
        "dossiers_summary_cust": "/api/v1/reports/dossiers/paid/summary-customer",
        "dossiers_totals_type": "/api/v1/reports/dossiers/paid/totals-by-type",
    }
    path = map_path.get(kind)
    if not path:
        _log(f"ERR invalid kind={kind}")
        return JSONResponse({"error": "invalid_kind"}, status_code=400)

    params: Dict[str, Any] = {}
    if project:
        params["project"] = project
    if "view/project-" in path and limit:
        params["limit"] = limit

    st, data = await _get_json(path, token, params)
    if st == 401:
        _log("AUTH 401 from Service A")
        return _unauth()
    if st != 200:
        _log(f"UPSTREAM non-200 status={st} body={_preview_body(data)}")
        return JSONResponse({"error": "service_a_failed", "status": st, "body": data}, status_code=502)
    return JSONResponse(data, status_code=200)
