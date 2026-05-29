from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Request, Query, Path
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.responses import RedirectResponse

from utils.templates import templates

SERVICE_A_BASE = os.getenv("SERVICE_A_BASE", "http://127.0.0.1:8824").rstrip("/")

router = APIRouter(prefix="/reports/group", tags=["reports-group"])


def _token(request: Request) -> str:
    return request.cookies.get("access_token") or request.cookies.get("token") or ""


def _headers(request: Request) -> Dict[str, str]:
    tok = _token(request)
    return {"Authorization": f"Bearer {tok}"} if tok else {}


async def _get_json(request: Request, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(
            f"{SERVICE_A_BASE}{path}",
            params=params or {},
            headers=_headers(request),
        )
        r.raise_for_status()
        return r.json()


async def _get_file(request: Request, path: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
    client = httpx.AsyncClient(timeout=90.0)
    r = await client.get(
        f"{SERVICE_A_BASE}{path}",
        params=params or {},
        headers=_headers(request),
    )
    r.raise_for_status()
    return r


def _ctx(
    request: Request,
    project_id: int,
    page: str,
    title: str,
    data: Any,
) -> Dict[str, Any]:
    return {
        "request": request,
        "project_id": project_id,
        "page": page,
        "title": title,
        "data": data,
    }


@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def group_report_home(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    return RedirectResponse(f"/reports/group/projects/{project_id}/summary", status_code=302)


@router.get("/projects/{project_id}/summary", response_class=HTMLResponse)
async def group_report_summary(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    data = await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/summary")
    return templates.TemplateResponse(
        "reports_group/summary.html",
        _ctx(request, project_id, "summary", "Tổng quan dự án nhóm", data),
    )


@router.get("/projects/{project_id}/groups", response_class=HTMLResponse)
async def group_report_groups(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    data = await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/groups")
    return templates.TemplateResponse(
        "reports_group/groups.html",
        _ctx(request, project_id, "groups", "Báo cáo theo nhóm cọc", data),
    )


@router.get("/projects/{project_id}/orders", response_class=HTMLResponse)
async def group_report_orders(
    request: Request,
    project_id: int = Path(..., ge=1),
    status: Optional[str] = Query(None),
    order_type: Optional[str] = Query(None),
):
    params = {"status": status, "order_type": order_type}
    data = await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/orders", params)
    return templates.TemplateResponse(
        "reports_group/orders.html",
        _ctx(request, project_id, "orders", "Danh sách đơn nhóm", data),
    )


@router.get("/projects/{project_id}/customers", response_class=HTMLResponse)
async def group_report_customers(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    data = await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/customers")
    return templates.TemplateResponse(
        "reports_group/customers.html",
        _ctx(request, project_id, "customers", "Báo cáo khách hàng nhóm", data),
    )


@router.get("/projects/{project_id}/eligible-slots", response_class=HTMLResponse)
async def group_report_eligible_slots(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    data = await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/eligible-slots")
    return templates.TemplateResponse(
        "reports_group/eligible_slots.html",
        _ctx(request, project_id, "eligible_slots", "Suất đủ điều kiện", data),
    )


@router.get("/projects/{project_id}/txns", response_class=HTMLResponse)
async def group_report_txns(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    data = await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/txns")
    return templates.TemplateResponse(
        "reports_group/txns.html",
        _ctx(request, project_id, "txns", "Giao dịch nhóm", data),
    )


# =========================
# JSON proxy
# =========================

@router.get("/api/projects/{project_id}/summary")
async def api_group_summary(request: Request, project_id: int):
    return JSONResponse(await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/summary"))


@router.get("/api/projects/{project_id}/groups")
async def api_group_groups(request: Request, project_id: int):
    return JSONResponse(await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/groups"))


@router.get("/api/projects/{project_id}/orders")
async def api_group_orders(
    request: Request,
    project_id: int,
    status: Optional[str] = Query(None),
    order_type: Optional[str] = Query(None),
):
    return JSONResponse(
        await _get_json(
            request,
            f"/api/v2/reports/group-auction/projects/{project_id}/orders",
            {"status": status, "order_type": order_type},
        )
    )


@router.get("/api/projects/{project_id}/customers")
async def api_group_customers(request: Request, project_id: int):
    return JSONResponse(await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/customers"))


@router.get("/api/projects/{project_id}/eligible-slots")
async def api_group_eligible_slots(request: Request, project_id: int):
    return JSONResponse(await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/eligible-slots"))


@router.get("/api/projects/{project_id}/txns")
async def api_group_txns(request: Request, project_id: int):
    return JSONResponse(await _get_json(request, f"/api/v2/reports/group-auction/projects/{project_id}/txns"))


@router.get("/api/projects/{project_id}/orders/{group_order_code}")
async def api_group_order_detail(
    request: Request,
    project_id: int,
    group_order_code: str,
):
    return JSONResponse(
        await _get_json(
            request,
            f"/api/v2/reports/group-auction/projects/{project_id}/orders/{group_order_code}",
        )
    )


# =========================
# XLSX export proxy
# =========================

@router.get("/api/projects/{project_id}/{report_name}/export")
async def api_group_export(
    request: Request,
    project_id: int,
    report_name: str,
):
    allowed = {"groups", "orders", "customers", "eligible-slots", "txns"}
    if report_name not in allowed:
        return JSONResponse({"error": "Invalid report_name"}, status_code=400)

    r = await _get_file(
        request,
        f"/api/v2/reports/group-auction/projects/{project_id}/{report_name}",
        {"format": "xlsx"},
    )

    filename = f"group_auction_{report_name}_p{project_id}.xlsx"
    return StreamingResponse(
        r.aiter_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        background=None,
    )

@router.get("", response_class=HTMLResponse)
async def group_reports_project_list(request: Request):
    data = await _get_json(
        request,
        "/api/v2/reports/group-auction/projects",
    )
    return templates.TemplateResponse(
        "reports_group/project_list.html",
        {
            "request": request,
            "title": "Báo cáo đấu nhóm",
            "projects": data.get("items") or data.get("projects") or [],
        },
    )