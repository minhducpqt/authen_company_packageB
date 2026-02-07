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

router = APIRouter(tags=["reports_v2"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

# ============================================================
# LIMITS / DEFAULTS
# ============================================================

MAX_LIMIT = 10000
DEFAULT_LIMIT = 1000
MIN_LIMIT = 1


# ============================================================
# Helpers
# ============================================================

def _clamp_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    if value is None:
        return default
    try:
        v = int(value)
    except Exception:
        return default
    if v < min_value:
        return min_value
    if v > max_value:
        return max_value
    return v


def _log(msg: str):
    print(f"[REPORTS_V2_B] {msg}")


async def _get_json(
    path: str,
    token: str,
    params: Dict[str, Any] | None = None,
):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}

    _log(f"→ GET {url} params={params or {}}")

    async with httpx.AsyncClient(timeout=60.0) as c:
        try:
            r = await c.get(url, headers=headers, params=params or {})
        except Exception as e:
            return 599, {"detail": str(e)}

    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"detail": r.text}


async def _proxy_xlsx(
    path: str,
    token: str,
    params: Dict[str, Any],
    filename: str,
) -> Response:
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    params = dict(params or {})
    params["format"] = "xlsx"

    _log(f"→ XLSX {url} params={params}")

    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.get(url, headers=headers, params=params)

    if r.status_code != 200:
        return Response(
            content=f"Service A error {r.status_code}".encode("utf-8"),
            status_code=502,
            media_type="text/plain; charset=utf-8",
        )

    return Response(
        content=r.content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


def _unauth():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


# ============================================================
# V2 – LÔ (LOTS)
# ============================================================

@router.get("/reports/v2/projects/{project_id}/lots/eligible", response_class=HTMLResponse)
async def lots_eligible_v2_page(
    request: Request,
    project_id: int,
    lot_code: Optional[str] = Query(None),
    limit: Optional[int] = Query(DEFAULT_LIMIT),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login", status_code=303)

    limit2 = _clamp_int(limit, DEFAULT_LIMIT, MIN_LIMIT, MAX_LIMIT)

    params = {"limit": limit2}
    if lot_code:
        params["lot_code"] = lot_code

    st, data = await _get_json(
        f"/api/v2/reports/projects/{project_id}/lots/eligible",
        token,
        params,
    )

    return templates.TemplateResponse(
        "reports_v2/lots_eligible.html",
        {
            "request": request,
            "project_id": project_id,
            "lot_code": lot_code or "",
            "limit": limit2,
            "data": data if st == 200 else {"items": [], "count": 0},
            "error": None if st == 200 else data,
        },
    )


@router.get("/reports/v2/projects/{project_id}/lots/eligible/export")
async def lots_eligible_v2_export(
    request: Request,
    project_id: int,
    lot_code: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    limit2 = _clamp_int(limit, DEFAULT_LIMIT, MIN_LIMIT, MAX_LIMIT)

    params = {"limit": limit2}
    if lot_code:
        params["lot_code"] = lot_code

    return await _proxy_xlsx(
        f"/api/v2/reports/projects/{project_id}/lots/eligible",
        token,
        params,
        filename=f"lots_eligible_project_{project_id}.xlsx",
    )


# ============================================================
# V2 – LÔ KHÔNG ĐỦ ĐIỀU KIỆN
# ============================================================

@router.get("/reports/v2/projects/{project_id}/lots/ineligible", response_class=HTMLResponse)
async def lots_ineligible_v2_page(
    request: Request,
    project_id: int,
    lot_code: Optional[str] = Query(None),
    limit: Optional[int] = Query(DEFAULT_LIMIT),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login", status_code=303)

    limit2 = _clamp_int(limit, DEFAULT_LIMIT, MIN_LIMIT, MAX_LIMIT)

    params = {"limit": limit2}
    if lot_code:
        params["lot_code"] = lot_code

    st, data = await _get_json(
        f"/api/v2/reports/projects/{project_id}/lots/ineligible",
        token,
        params,
    )

    return templates.TemplateResponse(
        "reports_v2/lots_ineligible.html",
        {
            "request": request,
            "project_id": project_id,
            "lot_code": lot_code or "",
            "limit": limit2,
            "data": data if st == 200 else {"items": [], "count": 0},
            "error": None if st == 200 else data,
        },
    )


# ============================================================
# V2 – KHÁCH HÀNG (CUSTOMERS)
# ============================================================

@router.get("/reports/v2/projects/{project_id}/customers/eligible", response_class=HTMLResponse)
async def customers_eligible_v2_page(
    request: Request,
    project_id: int,
    customer_cccd: Optional[str] = Query(None),
    limit: Optional[int] = Query(DEFAULT_LIMIT),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login", status_code=303)

    limit2 = _clamp_int(limit, DEFAULT_LIMIT, MIN_LIMIT, MAX_LIMIT)

    params = {"limit": limit2}
    if customer_cccd:
        params["customer_cccd"] = customer_cccd

    st, data = await _get_json(
        f"/api/v2/reports/projects/{project_id}/customers/eligible",
        token,
        params,
    )

    return templates.TemplateResponse(
        "reports_v2/customers_eligible.html",
        {
            "request": request,
            "project_id": project_id,
            "customer_cccd": customer_cccd or "",
            "limit": limit2,
            "data": data if st == 200 else {"items": [], "count": 0},
            "error": None if st == 200 else data,
        },
    )


@router.get("/reports/v2/projects/{project_id}/customers/ineligible", response_class=HTMLResponse)
async def customers_ineligible_v2_page(
    request: Request,
    project_id: int,
    customer_cccd: Optional[str] = Query(None),
    limit: Optional[int] = Query(DEFAULT_LIMIT),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login", status_code=303)

    limit2 = _clamp_int(limit, DEFAULT_LIMIT, MIN_LIMIT, MAX_LIMIT)

    params = {"limit": limit2}
    if customer_cccd:
        params["customer_cccd"] = customer_cccd

    st, data = await _get_json(
        f"/api/v2/reports/projects/{project_id}/customers/ineligible",
        token,
        params,
    )

    return templates.TemplateResponse(
        "reports_v2/customers_ineligible.html",
        {
            "request": request,
            "project_id": project_id,
            "customer_cccd": customer_cccd or "",
            "limit": limit2,
            "data": data if st == 200 else {"items": [], "count": 0},
            "error": None if st == 200 else data,
        },
    )


# ============================================================
# JSON proxy (cho FE / mobile sau này)
# ============================================================

@router.get("/api/reports/v2/{kind}", response_class=JSONResponse)
async def reports_v2_api_proxy(
    request: Request,
    kind: str,
    project_id: int = Query(...),
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    map_path = {
        "lots_eligible":   f"/api/v2/reports/projects/{project_id}/lots/eligible",
        "lots_ineligible": f"/api/v2/reports/projects/{project_id}/lots/ineligible",
        "customers_ok":    f"/api/v2/reports/projects/{project_id}/customers/eligible",
        "customers_bad":   f"/api/v2/reports/projects/{project_id}/customers/ineligible",
    }

    path = map_path.get(kind)
    if not path:
        return JSONResponse({"error": "invalid_kind"}, status_code=400)

    st, data = await _get_json(path, token, {})
    if st != 200:
        return JSONResponse(
            {"error": "service_a_failed", "status": st, "body": data},
            status_code=502,
        )

    return JSONResponse(data, status_code=200)
