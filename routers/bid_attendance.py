# routers/bid_attendance.py

from __future__ import annotations
from typing import Optional, Dict, Any, List
from urllib.parse import quote

import os
import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/bid-attendance", tags=["bid_attendance"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    params: dict,
):
    r = await client.get(url, headers=headers, params=params)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


# ======================================================================
# PAGE: DANH SÁCH ĐIỂM DANH
# ======================================================================
@router.get("", response_class=HTMLResponse)
async def bid_attendance_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    customer_q: Optional[str] = Query(
        None, description="Tên khách / CCCD / điện thoại"
    ),
    page: int = Query(1, ge=1),
    size: int = Query(500, ge=1, le=5000),
):
    """
    Màn hình 4.1: Danh sách điểm danh khách đủ điều kiện tham gia đấu giá.
    Dữ liệu lấy từ Service A: /api/v1/report/bid_tickets/customers
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote('/bid-attendance')}",
            status_code=303,
        )

    params: Dict[str, Any] = {
        "page": page,
        "size": size,
    }
    if project_code:
        params["project_code"] = project_code
    if customer_q:
        params["customer_q"] = customer_q

    headers = {"Authorization": f"Bearer {token}"}
    data: Dict[str, Any] = {"data": [], "page": page, "size": size, "total": 0}
    load_err: Optional[str] = None

    try:
        async with httpx.AsyncClient(
            base_url=SERVICE_A_BASE_URL, timeout=20.0
        ) as client:
            st, js = await _get_json(
                client, "/api/v1/report/bid_tickets/customers", headers, params
            )
            if st == 200 and isinstance(js, dict):
                data = js
            else:
                load_err = (
                    f"Không tải được danh sách khách đủ điều kiện (HTTP {st})."
                )
    except Exception as e:
        load_err = str(e)

    customers: List[Dict[str, Any]] = data.get("data") or []

    # Đảm bảo sort theo project_code, rồi STT (điểm danh)
    customers.sort(
        key=lambda c: (
            c.get("project_code") or "",
            c.get("stt") or 10**9,
        )
    )

    return templates.TemplateResponse(
        "pages/bid_attendance/index.html",
        {
            "request": request,
            "title": "Danh sách điểm danh",
            "me": me,
            "filters": {
                "project_code": project_code or "",
                "customer_q": customer_q or "",
            },
            "page": data,
            "customers": customers,
            "load_err": load_err,
        },
    )


# ======================================================================
# PRINT: DANH SÁCH ĐIỂM DANH (A4)
# ======================================================================
@router.get("/print", response_class=HTMLResponse)
async def print_bid_attendance(
    request: Request,
    project_code: str = Query(..., description="Mã dự án cần in danh sách"),
):
    """
    In danh sách điểm danh cho 1 dự án:
      - Dùng /api/v1/report/bid_tickets/customers?project_code=...&page=1&size=5000
      - Sort theo STT
      - Render template print.html
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote('/bid-attendance')}",
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "project_code": project_code,
        "page": 1,
        "size": 5000,
    }

    try:
        async with httpx.AsyncClient(
            base_url=SERVICE_A_BASE_URL, timeout=30.0
        ) as client:
            r = await client.get(
                "/api/v1/report/bid_tickets/customers",
                headers=headers,
                params=params,
            )
        if r.status_code != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không lấy được danh sách khách (HTTP {r.status_code}).</p>",
                status_code=500,
            )
        js = r.json() or {}
        customers: List[Dict[str, Any]] = js.get("data") or []
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not customers:
        return HTMLResponse(
            "<h1>Không có khách nào đủ điều kiện trong dự án này để in.</h1>",
            status_code=404,
        )

    # Sort theo STT
    customers.sort(
        key=lambda c: (
            c.get("project_code") or "",
            c.get("stt") or 10**9,
        )
    )

    return templates.TemplateResponse(
        "pages/bid_attendance/print.html",
        {
            "request": request,
            "me": me,
            "project_code": project_code,
            "customers": customers,
        },
    )
