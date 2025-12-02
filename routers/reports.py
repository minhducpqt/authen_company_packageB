# routers/reports.py
from __future__ import annotations
import os
from typing import Optional, Dict, Any, List, Tuple

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)

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


# ---------- HTTP helpers ----------
async def _get_json(
    path: str,
    token: str,
    params: Dict[str, Any] | List[Tuple[str, Any]] | None = None,
):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ GET JSON {url} params={params or {}}")

    async with httpx.AsyncClient(timeout=60.0) as c:
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


async def _proxy_xlsx(
    path: str,
    token: str,
    params: Dict[str, Any],
    filename: str,
) -> Response:
    """
    Gọi Service A trả về file XLSX, rồi stream lại cho browser.
    BẮT BUỘC gắn Authorization Bearer từ token.
    """
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    params = dict(params or {})
    params["format"] = "xlsx"  # ép đúng format để A trả file

    _log(f"→ GET XLSX {url} params={params}")
    async with httpx.AsyncClient(timeout=120.0) as c:
        try:
            r = await c.get(url, headers=headers, params=params)
        except Exception as e:
            _log(f"← EXC XLSX {url} error={e}")
            return Response(
                content=f"Lỗi kết nối Service A: {e}".encode("utf-8"),
                status_code=502,
                media_type="text/plain; charset=utf-8",
            )

    if r.status_code != 200:
        _log(f"← XLSX non-200 {r.status_code} body={_preview_body(r.text)}")
        return Response(
            content=f"Service A trả về lỗi {r.status_code} khi export XLSX".encode("utf-8"),
            status_code=502,
            media_type="text/plain; charset=utf-8",
        )

    disp = f'attachment; filename="{filename}"'
    return Response(
        content=r.content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": disp},
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


# ============================================================
# 5.0 Tổng quan
# ============================================================
@router.get("/reports", response_class=HTMLResponse)
async def reports_home(request: Request):
    _log(f"REQ /reports url={request.url}")

    # 1. Lấy access token từ cookie
    token = get_access_token(request)
    if not token:
        _log("AUTH missing → redirect /login")
        return RedirectResponse(
            url="/login?next=%2Freports",
            status_code=303,
        )

    # 2. Load danh sách dự án ACTIVE
    projects: list[dict] = []
    try:
        status, data = await _get_json(
            "/api/v1/projects",
            token,
            {"status": "ACTIVE", "size": 1000},
        )
        if status == 200 and isinstance(data, dict):
            projects = data.get("data") or data.get("items") or []
    except Exception as e:
        _log(f"reports_home: load projects error={e!r}")

    # 3. Render template
    return templates.TemplateResponse(
        "reports/index.html",
        {
            "request": request,
            "title": "Báo cáo thống kê",
            "projects": projects,
        },
    )


# ============================================================
# 5.1 LÔ & ĐIỀU KIỆN (VIEW /view/project-lots-*)
# ============================================================

@router.get("/reports/lots/eligible", response_class=HTMLResponse)
async def lots_eligible_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    lot_code: Optional[str] = Query(None, description="Prefix mã lô, ví dụ: CL03"),
    limit: Optional[int] = Query(5000, ge=1, le=5000, description="Giới hạn số dòng tối đa"),
):
    """
    Lô đủ điều kiện (≥ 2 khách).
    Gọi Service A: /api/v1/reports/view/project-lots-eligible
    """
    _log(f"REQ /reports/lots/eligible url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Freports%2Flots%2Feligible",
            status_code=303,
        )

    projects, selected_project = await _load_projects(token, project)
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    if selected_project:
        params: Dict[str, Any] = {"project": selected_project}
        if lot_code:
            params["lot_code"] = lot_code
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
        "lot_code": lot_code or "",
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/lots_eligible.html", ctx)


@router.get("/reports/lots/eligible/export")
async def lots_eligible_export(
    request: Request,
    project: str = Query(..., description="project_code như KIDO6"),
    lot_code: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    params: Dict[str, Any] = {"project": project}
    if lot_code:
        params["lot_code"] = lot_code
    if limit is not None:
        params["limit"] = limit

    filename = f"project_lots_eligible_{project}.xlsx"
    return await _proxy_xlsx("/api/v1/reports/view/project-lots-eligible", token, params, filename)


@router.get("/reports/lots/ineligible", response_class=HTMLResponse)
async def lots_ineligible_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    lot_code: Optional[str] = Query(None, description="Prefix mã lô, ví dụ: CL03"),
    limit: Optional[int] = Query(5000, ge=1, le=5000, description="Giới hạn số dòng tối đa"),
):
    """
    Lô KHÔNG đủ điều kiện (0–1 khách).
    Gọi Service A: /api/v1/reports/view/project-lots-not-eligible
    """
    _log(f"REQ /reports/lots/ineligible url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Freports%2Flots%2Fineligible",
            status_code=303,
        )

    projects, selected_project = await _load_projects(token, project)
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    if selected_project:
        params: Dict[str, Any] = {"project": selected_project}
        if lot_code:
            params["lot_code"] = lot_code
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
        "lot_code": lot_code or "",
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/lots_ineligible.html", ctx)


@router.get("/reports/lots/ineligible/export")
async def lots_ineligible_export(
    request: Request,
    project: str = Query(..., description="project_code như KIDO6"),
    lot_code: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    params: Dict[str, Any] = {"project": project}
    if lot_code:
        params["lot_code"] = lot_code
    if limit is not None:
        params["limit"] = limit

    filename = f"project_lots_not_eligible_{project}.xlsx"
    return await _proxy_xlsx("/api/v1/reports/view/project-lots-not-eligible", token, params, filename)


# ---------- 5.1b: Thống kê tiền đặt trước từng lô ----------

@router.get("/reports/lots/deposit-stats", response_class=HTMLResponse)
async def lots_deposit_stats_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    lot_code: Optional[str] = Query(None, description="Prefix mã lô"),
    min_customers: Optional[int] = Query(None, ge=0),
    max_customers: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(1000, ge=1, le=10000),
):
    """
    Thống kê tiền đặt trước theo từng lô.
    VIEW: /api/v1/reports/view/project-lot-deposit-stats
    """
    _log(f"REQ /reports/lots/deposit-stats url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Freports%2Flots%2Fdeposit-stats",
            status_code=303,
        )

    projects, selected_project = await _load_projects(token, project)
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    if selected_project:
        params: Dict[str, Any] = {"project": selected_project}
        if lot_code:
            params["lot_code"] = lot_code
        if min_customers is not None:
            params["min_customers"] = min_customers
        if max_customers is not None:
            params["max_customers"] = max_customers
        if limit is not None:
            params["limit"] = limit

        st, js = await _get_json("/api/v1/reports/view/project-lot-deposit-stats", token, params)
        if st == 200:
            data = js
        else:
            error = {"status": st, "body": js}

    ctx = {
        "request": request,
        "title": "Thống kê tiền đặt trước từng lô",
        "projects": projects,
        "project": selected_project,
        "lot_code": lot_code or "",
        "min_customers": min_customers,
        "max_customers": max_customers,
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/lots_deposit_stats.html", ctx)


@router.get("/reports/lots/deposit-stats/export")
async def lots_deposit_stats_export(
    request: Request,
    project: str = Query(..., description="project_code như KIDO6"),
    lot_code: Optional[str] = Query(None),
    min_customers: Optional[int] = Query(None),
    max_customers: Optional[int] = Query(None),
    limit: Optional[int] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    params: Dict[str, Any] = {"project": project}
    if lot_code:
        params["lot_code"] = lot_code
    if min_customers is not None:
        params["min_customers"] = min_customers
    if max_customers is not None:
        params["max_customers"] = max_customers
    if limit is not None:
        params["limit"] = limit

    filename = f"project_lot_deposit_stats_{project}.xlsx"
    return await _proxy_xlsx("/api/v1/reports/view/project-lot-deposit-stats", token, params, filename)


# ============================================================
# 5.2 KHÁCH HÀNG & ĐIỀU KIỆN (VIEW /view/project-customers-*)
# ============================================================

@router.get("/reports/customers/eligible-lots", response_class=HTMLResponse)
async def customers_eligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None, description="Exact CCCD"),
    lot_code: Optional[str] = Query(None, description="Prefix mã lô"),
    limit: Optional[int] = Query(5000, ge=1, le=5000),
):
    """
    Khách + lô đủ điều kiện.
    Gọi Service A: /api/v1/reports/view/project-customers-lots-eligible
    """
    _log(f"REQ /reports/customers/eligible-lots url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Freports%2Fcustomers%2Feligible-lots",
            status_code=303,
        )

    projects, selected_project = await _load_projects(token, project)
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    if selected_project:
        params: Dict[str, Any] = {
            "project": selected_project,
            "expose_phone": "true",
        }
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if lot_code:
            params["lot_code"] = lot_code
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
        "lot_code": lot_code or "",
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/customers_eligible.html", ctx)


@router.get("/reports/customers/eligible-lots/export")
async def customers_eligible_lots_export(
    request: Request,
    project: str = Query(..., description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None),
    lot_code: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    params: Dict[str, Any] = {
        "project": project,
        "expose_phone": "true",
    }
    if customer_cccd:
        params["customer_cccd"] = customer_cccd
    if lot_code:
        params["lot_code"] = lot_code
    if limit is not None:
        params["limit"] = limit

    filename = f"project_customers_lots_eligible_{project}.xlsx"
    return await _proxy_xlsx("/api/v1/reports/view/project-customers-lots-eligible", token, params, filename)


@router.get("/reports/customers/not-eligible-lots", response_class=HTMLResponse)
async def customers_ineligible_lots_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None, description="Exact CCCD"),
    lot_code: Optional[str] = Query(None, description="Prefix mã lô"),
    limit: Optional[int] = Query(5000, ge=1, le=5000),
):
    """
    Khách + lô KHÔNG đủ điều kiện.
    Gọi Service A: /api/v1/reports/view/project-customers-lots-not-enough
    """
    _log(f"REQ /reports/customers/not-eligible-lots url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Freports%2Fcustomers%2Fnot-eligible-lots",
            status_code=303,
        )

    projects, selected_project = await _load_projects(token, project)
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    if selected_project:
        params: Dict[str, Any] = {
            "project": selected_project,
            "expose_phone": "true",
        }
        if customer_cccd:
            params["customer_cccd"] = customer_cccd
        if lot_code:
            params["lot_code"] = lot_code
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
        "lot_code": lot_code or "",
        "limit": limit,
        "data": data or {"items": [], "count": 0},
        "error": error,
    }
    return templates.TemplateResponse("reports/customers_ineligible.html", ctx)


@router.get("/reports/customers/not-eligible-lots/export")
async def customers_ineligible_lots_export(
    request: Request,
    project: str = Query(..., description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None),
    lot_code: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    params: Dict[str, Any] = {
        "project": project,
        "expose_phone": "true",
    }
    if customer_cccd:
        params["customer_cccd"] = customer_cccd
    if lot_code:
        params["lot_code"] = lot_code
    if limit is not None:
        params["limit"] = limit

    filename = f"project_customers_lots_not_enough_{project}.xlsx"
    return await _proxy_xlsx("/api/v1/reports/view/project-customers-lots-not-enough", token, params, filename)


# ============================================================
# 5.3 MUA HỒ SƠ
# ============================================================

@router.get("/reports/dossiers/paid/detail", response_class=HTMLResponse)
async def dossiers_paid_detail_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None, description="Exact CCCD"),
    limit: Optional[int] = Query(1000, ge=1, le=10000),
):
    """
    Chi tiết các đơn mua hồ sơ theo khách & đơn.
    Dùng VIEW: /api/v1/reports/view/project-dossier-items
    """
    _log(f"REQ /reports/dossiers/paid/detail url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fdetail",
            status_code=303,
        )

    projects, selected_project = await _load_projects(token, project)
    data: Dict[str, Any] | None = None
    error: Dict[str, Any] | None = None

    if selected_project:
        params: Dict[str, Any] = {
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


@router.get("/reports/dossiers/paid/detail/export")
async def dossiers_paid_detail_export(
    request: Request,
    project: str = Query(..., description="project_code như KIDO6"),
    customer_cccd: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    params: Dict[str, Any] = {
        "project": project,
        "expose_phone": "true",
    }
    if customer_cccd:
        params["customer_cccd"] = customer_cccd
    if limit is not None:
        params["limit"] = limit

    filename = f"project_dossier_items_{project}.xlsx"
    return await _proxy_xlsx("/api/v1/reports/view/project-dossier-items", token, params, filename)


@router.get("/reports/dossiers/paid/summary", response_class=HTMLResponse)
async def dossiers_paid_summary_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
):
    """
    Tổng hợp mua hồ sơ:
    - /api/v1/reports/dossiers/paid/summary-customer
    - /api/v1/reports/dossiers/paid/totals-by-type
    """
    _log(f"REQ /reports/dossiers/paid/summary url={request.url}")
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Freports%2Fdossiers%2Fpaid%2Fsummary",
            status_code=303,
        )

    projects, selected_project = await _load_projects(token, project)

    data_summary_customer: Dict[str, Any] | None = None
    data_totals_type: Dict[str, Any] | None = None
    st1 = st2 = None

    if selected_project:
        # ✅ bật expose_phone để Service A fill phone/email
        params = {"project": selected_project, "expose_phone": "true"}
        st1, data1 = await _get_json(
            "/api/v1/reports/dossiers/paid/summary-customer", token, params
        )
        # totals-by-type không cần phone/email
        st2, data2 = await _get_json(
            "/api/v1/reports/dossiers/paid/totals-by-type", token, {"project": selected_project}
        )
        if st1 == 200:
            data_summary_customer = data1
        if st2 == 200:
            data_totals_type = data2

    data = {
        "summary_customer": data_summary_customer or {"items": [], "count": 0, "status": st1},
        "totals_by_type": data_totals_type or {"items": [], "count": 0, "status": st2},
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
    return templates.TemplateResponse(
        "reports/dossiers_paid.html",
        ctx,
        status_code=200 if ok else 502,
    )


@router.get("/reports/dossiers/paid/summary/customer/export")
async def dossiers_paid_summary_customer_export(
    request: Request,
    project: str = Query(..., description="project_code như KIDO6"),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    # ✅ bật expose_phone cho export
    params = {"project": project, "expose_phone": "true"}
    filename = f"dossier_summary_customer_{project}.xlsx"
    return await _proxy_xlsx(
        "/api/v1/reports/dossiers/paid/summary-customer", token, params, filename
    )


@router.get("/reports/dossiers/paid/summary/types/export")
async def dossiers_paid_totals_type_export(
    request: Request,
    project: str = Query(..., description="project_code như KIDO6"),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    params = {"project": project}
    filename = f"dossier_totals_by_type_{project}.xlsx"
    return await _proxy_xlsx("/api/v1/reports/dossiers/paid/totals-by-type", token, params, filename)


# ---------- JSON proxy cũ (back-compat nếu FE khác đang dùng) ----------
@router.get("/api/reports/{kind}", response_class=JSONResponse)
async def reports_api(
    request: Request,
    kind: str,
    project: Optional[str] = Query(None, description="project_code như KIDO6"),
):
    _log(f"REQ /api/reports/{kind} url={request.url}")
    token = get_access_token(request)
    if not token:
        return _unauth()

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
        return JSONResponse({"error": "invalid_kind"}, status_code=400)

    params: Dict[str, Any] = {}
    if project:
        params["project"] = project

    st, data = await _get_json(path, token, params)
    if st == 401:
        return _unauth()
    if st != 200:
        return JSONResponse({"error": "service_a_failed", "status": st, "body": data}, status_code=502)
    return JSONResponse(data, status_code=200)
