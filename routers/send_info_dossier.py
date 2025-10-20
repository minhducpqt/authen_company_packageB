# routers/send_info_dossier.py
from __future__ import annotations
from typing import Optional, List, Tuple

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import httpx

from utils.templates import templates
from utils.auth import get_access_token
from services.orders_client import orders_client
import os

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter(tags=["send-info"])

# Optional helper (như bạn đang dùng ở module khác)
async def _api_get(client: httpx.AsyncClient, path: str, token: str, params: List[Tuple[str, str | int]] | None = None):
    return await client.get(
        f"{SERVICE_A_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        timeout=20.0,
    )

@router.get("/thong-tin-khach-mua-ho-so", response_class=HTMLResponse)
async def dossier_orders_page(
    request: Request,
    project_id: Optional[int] = Query(None, ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=200),
):
    """
    Trang 4.1 — SSR sẵn lần đầu:
    - Lấy list projects ACTIVE (để render dropdown)
    - Nếu chỉ có 1 project ACTIVE -> auto chọn
    - Gọi /api/v1/dossier-orders để render bảng lần đầu
    """
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fthong-tin-khach-mua-ho-so", status_code=303)

    # 1) Danh sách dự án ACTIVE
    code_proj, data_proj = await orders_client.list_active_projects(token, size=1000)
    projects = (data_proj or {}).get("data") if isinstance(data_proj, dict) else None
    projects = projects or []

    # Auto-select nếu chỉ có 1 project active
    resolved_project_id = project_id
    if not resolved_project_id and len(projects) == 1:
        try:
            resolved_project_id = int(projects[0]["id"])
        except Exception:
            resolved_project_id = None

    # 2) Gọi list dossier-orders
    code_orders, data_orders = await orders_client.list_dossier_orders(
        token,
        page=page,
        size=size,
        project_id=resolved_project_id,
    )
    page_obj = data_orders if isinstance(data_orders, dict) else {"data": [], "page": page, "size": size, "total": 0}

    # Chuẩn hóa đề phòng thiếu field
    page_obj.setdefault("data", [])
    page_obj.setdefault("page", page)
    page_obj.setdefault("size", size)
    page_obj.setdefault("total", 0)

    filters = {
        "project_id": resolved_project_id or "",
    }

    return templates.TemplateResponse(
        "send/dossier_orders.html",
        {
            "request": request,
            "title": "4.1 Khách mua hồ sơ",
            "projects": projects,
            "filters": filters,
            "page": page_obj,
        },
    )

@router.get("/thong-tin-khach-mua-ho-so/data", response_class=JSONResponse)
async def dossier_orders_data(
    request: Request,
    project_id: Optional[int] = Query(None, ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=200),
    status: Optional[str] = Query(None),
    customer_id: Optional[int] = Query(None, ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    code, data = await orders_client.list_dossier_orders(
        token, page=page, size=size, status=status, customer_id=customer_id, project_id=project_id
    )
    if code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if code >= 500:
        return JSONResponse({"error": "server"}, status_code=502)

    # Đảm bảo có cấu trúc page chuẩn
    if not isinstance(data, dict):
        data = {"data": [], "page": page, "size": size, "total": 0}
    data.setdefault("data", [])
    data.setdefault("page", page)
    data.setdefault("size", size)
    data.setdefault("total", 0)

    return JSONResponse(data, status_code=200)
