# routers/bid_tickets.py (Service B - Admin)

from __future__ import annotations
from typing import Optional, Dict, Any, List
from urllib.parse import quote

import os
import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/bid-tickets", tags=["bid_tickets"])

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
# PAGE: INDEX
# ======================================================================
@router.get("", response_class=HTMLResponse)
async def bid_tickets_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    customer_q: Optional[str] = Query(None, description="Tên khách / CCCD / điện thoại"),
    lot_code: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=1000),
):
    """
    Màn hình quản lý/in phiếu trả giá.
    - Tab 1: Theo KHÁCH (group theo customer_id, có STT)
    - Tab 2: Theo LÔ (dữ liệu thô từng lô)
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote('/bid-tickets')}",
            status_code=303,
        )

    params: Dict[str, Any] = {
        "page": page,
        "size": size,
    }
    if project_code:
        params["project_code"] = project_code
    if lot_code:
        params["lot_code"] = lot_code
    if customer_q:
        params["customer_q"] = customer_q

    headers = {"Authorization": f"Bearer {token}"}
    data: Dict[str, Any] = {"data": [], "page": page, "size": size, "total": 0}
    load_err: Optional[str] = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
            st, js = await _get_json(client, "/api/v1/report/bid_tickets", headers, params)
            if st == 200 and isinstance(js, dict):
                data = js
            else:
                load_err = f"Không tải được dữ liệu phiếu trả giá (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    rows: List[Dict[str, Any]] = data.get("data") or []

    # Group theo khách
    customers: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        cid = r.get("customer_id")
        if cid is None:
            continue
        if cid not in customers:
            customers[cid] = {
                "customer_id": cid,
                "customer_full_name": r.get("customer_full_name"),
                "cccd": r.get("cccd"),
                "phone": r.get("phone"),
                "email": r.get("email"),
                "address": r.get("address"),
                "total_deposit_amount_per_customer_project": r.get(
                    "total_deposit_amount_per_customer_project"
                ),
                "project_code": r.get("project_code"),
                "project_name": r.get("project_name"),
                # STT theo dự án (do Service A tính trong v_report_bid_customers)
                "stt": r.get("stt"),
                "stt_padded": r.get("stt_padded"),
                "lots": [],
            }
        customers[cid]["lots"].append(r)

    customers_list = list(customers.values())

    # Sort customers_list theo project_code, rồi STT (đảm bảo đúng thứ tự điểm danh)
    customers_list.sort(
        key=lambda c: (
            c.get("project_code") or "",
            c.get("stt") or 10**9,
        )
    )

    return templates.TemplateResponse(
        "pages/bid_tickets/index.html",
        {
            "request": request,
            "title": "Phiếu trả giá",
            "me": me,
            "filters": {
                "project_code": project_code or "",
                "customer_q": customer_q or "",
                "lot_code": lot_code or "",
            },
            "page": data,
            "rows": rows,
            "customers": customers_list,
            "load_err": load_err,
        },
    )


# ======================================================================
# PRINT: 1 KH + 1 LÔ / N LÔ CỦA 1 KH
# ======================================================================
@router.get("/print", response_class=HTMLResponse)
async def print_bid_tickets(
    request: Request,
    project_code: str = Query(...),
    customer_id: int = Query(...),
    lot_id: Optional[int] = Query(None),
):
    """
    In phiếu:
    - Nếu truyền lot_id -> in 1 phiếu (1 khách+1 lô)
    - Nếu KHÔNG truyền lot_id -> in tất cả phiếu cho khách này trong dự án (N trang)
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote('/bid-tickets')}",
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}

    # Lấy dữ liệu từ Service A
    if lot_id is not None:
        # 1 phiếu
        params = {
            "project_code": project_code,
            "customer_id": customer_id,
            "lot_id": lot_id,
        }
        try:
            async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=15.0) as client:
                r = await client.get("/api/v1/report/bid_tickets/one", headers=headers, params=params)
            if r.status_code != 200:
                return HTMLResponse(
                    f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu (HTTP {r.status_code}).</p>",
                    status_code=500,
                )
            js = r.json() or {}
            rows: List[Dict[str, Any]] = [js.get("data") or {}]
        except Exception as e:
            return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)
    else:
        # N phiếu cho khách này
        params = {
            "project_code": project_code,
            "customer_id": customer_id,
            "page": 1,
            "size": 1000,
        }
        try:
            async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
                r = await client.get("/api/v1/report/bid_tickets", headers=headers, params=params)
            if r.status_code != 200:
                return HTMLResponse(
                    f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu (HTTP {r.status_code}).</p>",
                    status_code=500,
                )
            js = r.json() or {}
            rows = js.get("data") or []
        except Exception as e:
            return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not rows:
        return HTMLResponse("<h1>Không có dữ liệu phiếu để in.</h1>", status_code=404)

    # Service A đã sort theo project_code, stt, customer_full_name, lot_code
    # ở đây vẫn có thể đảm bảo lại thứ tự theo lot_code cho 1 khách
    rows.sort(
        key=lambda t: (
            t.get("stt") or 10**9,
            t.get("customer_id") or 10**9,
            t.get("lot_code") or "",
        )
    )

    return templates.TemplateResponse(
        "pages/bid_tickets/print.html",
        {
            "request": request,
            "me": me,
            "tickets": rows,  # mỗi phần tử = 1 phiếu
        },
    )


# ======================================================================
# PRINT-ALL: TOÀN BỘ KHÁCH / LÔ TRONG 1 DỰ ÁN (1 TAB, N TRANG)
# ======================================================================
@router.get("/print-all", response_class=HTMLResponse)
async def print_all_bid_tickets(
    request: Request,
    project_code: str = Query(...),
):
    """
    In tất cả phiếu trả giá của TẤT CẢ khách đủ điều kiện trong 1 dự án.
    - Lấy từ Service A: /api/v1/report/bid_tickets?project_code=...&page=1&size=5000
    - Sort theo STT (điểm danh) rồi theo mã lô để in đúng thứ tự.
    - Render chung bằng template print.html (mỗi phiếu = 1 trang A4).
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        # quay lại màn hình login, giữ next để quay lại trang list
        return RedirectResponse(
            url=f"/login?next={quote('/bid-tickets')}",
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "project_code": project_code,
        "page": 1,
        "size": 5000,  # đủ lớn cho 1 dự án
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
            r = await client.get("/api/v1/report/bid_tickets", headers=headers, params=params)
        if r.status_code != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu (HTTP {r.status_code}).</p>",
                status_code=500,
            )
        js = r.json() or {}
        rows: List[Dict[str, Any]] = js.get("data") or []
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not rows:
        return HTMLResponse("<h1>Không có phiếu nào trong dự án này để in.</h1>", status_code=404)

    # Đảm bảo thứ tự in:
    #  - Theo STT (điểm danh) của khách trong dự án
    #  - Rồi theo mã lô (để các lô của 1 khách đi liền nhau, có thứ tự dễ kiểm)
    rows.sort(
        key=lambda t: (
            t.get("stt") or 10**9,
            t.get("customer_id") or 10**9,
            t.get("lot_code") or "",
        )
    )

    return templates.TemplateResponse(
        "pages/bid_tickets/print.html",
        {
            "request": request,
            "me": me,
            "tickets": rows,
        },
    )
