# routers/bid_tickets.py (Service B - Admin)

from __future__ import annotations
from typing import Optional, Dict, Any, List, Tuple
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


def _parse_item(s: str) -> Optional[Tuple[str, int, int]]:
    """
    item format: "<project_code>|<customer_id>|<lot_id>"
    """
    try:
        parts = (s or "").split("|")
        if len(parts) != 3:
            return None
        pj = (parts[0] or "").strip()
        cid = int(parts[1])
        lid = int(parts[2])
        if not pj or cid <= 0 or lid <= 0:
            return None
        return pj, cid, lid
    except Exception:
        return None


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
    size: int = Query(10000, ge=1, le=10000),
):
    """
    Màn hình quản lý/in phiếu trả giá.
    - Tab 1: Theo KHÁCH (group theo customer_id)
    - Tab 2: Theo LÔ (group theo lot_id, sort lot_id asc, customers asc)
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

    # -----------------------------
    # TAB 1: Group theo khách
    # -----------------------------
    customers: Dict[int, Dict[str, Any]] = {}
    for r in rows:
        cid = r.get("customer_id")
        if cid is None:
            continue
        cid = int(cid)
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
                "stt": r.get("stt"),
                "stt_padded": r.get("stt_padded"),
                "lots": [],
            }
        customers[cid]["lots"].append(r)

    customers_list = list(customers.values())
    customers_list.sort(
        key=lambda c: (
            c.get("project_code") or "",
            c.get("stt") or 10**9,
        )
    )

    # -----------------------------
    # TAB 2: Group theo lô
    # - sort lots by lot_id asc
    # - inside each lot: customers sort by customer_id asc
    # -----------------------------
    lots_map: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for r in rows:
        pj = (r.get("project_code") or "").strip()
        lid = r.get("lot_id")
        if not pj or lid is None:
            continue
        lid = int(lid)
        key = (pj, lid)
        if key not in lots_map:
            lots_map[key] = {
                "project_code": pj,
                "project_name": r.get("project_name"),
                "project_id": r.get("project_id"),
                "auction_mode": r.get("auction_mode"),

                "lot_id": lid,
                "lot_code": r.get("lot_code"),
                "lot_description": r.get("lot_description"),
                "area_m2": r.get("area_m2"),
                "starting_price_vnd": r.get("starting_price_vnd"),
                "bid_step_vnd": r.get("bid_step_vnd"),
                "deposit_amount_vnd": r.get("deposit_amount_vnd"),
                "lot_status": r.get("lot_status"),

                "deposit_customer_count": r.get("deposit_customer_count"),
                "total_deposit_amount_per_lot": r.get("total_deposit_amount_per_lot"),

                "customers": [],
            }

        # push customer-row
        lots_map[key]["customers"].append(r)

    lots_list = list(lots_map.values())
    lots_list.sort(key=lambda l: (l.get("lot_id") or 10**18, l.get("lot_code") or ""))

    for l in lots_list:
        l["customers"].sort(key=lambda rr: (rr.get("customer_id") or 10**18))

    lots_total = len(lots_list)
    pairs_total = len(rows)

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
            "rows": rows,              # vẫn giữ nếu anh cần debug
            "customers": customers_list,
            "lots": lots_list,         # ✅ NEW: tab theo lô dùng cái này
            "lots_total": lots_total,
            "pairs_total": pairs_total,
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

    if lot_id is not None:
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


# ======================================================================
# PRINT-ALL: TOÀN BỘ KHÁCH / LÔ TRONG 1 DỰ ÁN
# ======================================================================
@router.get("/print-all", response_class=HTMLResponse)
async def print_all_bid_tickets(
    request: Request,
    project_code: str = Query(...),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote('/bid-tickets')}",
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "project_code": project_code,
        "page": 1,
        "size": 10000,
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


# ======================================================================
# PRINT-SELECTED: IN N PHIẾU ĐÃ CHỌN (1 POPUP, N TRANG)
# ======================================================================
@router.get("/print-selected", response_class=HTMLResponse)
async def print_selected_bid_tickets(
    request: Request,
    item: List[str] = Query(..., description="Repeated: project|customer_id|lot_id"),
):
    """
    In các phiếu đã chọn (tab Theo LÔ):
    - Nhận nhiều item=project|customer|lot
    - Backend gom tickets -> render print.html (mỗi ticket = 1 trang)
    - Chỉ mở 1 popup => không bị popup blocker
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote('/bid-tickets')}",
            status_code=303,
        )

    parsed: List[Tuple[str, int, int]] = []
    seen = set()
    for s in item or []:
        tup = _parse_item(s)
        if not tup:
            continue
        if tup in seen:
            continue
        seen.add(tup)
        parsed.append(tup)

    if not parsed:
        return HTMLResponse("<h1>Không có phiếu hợp lệ để in.</h1>", status_code=400)

    headers = {"Authorization": f"Bearer {token}"}

    async def _fetch_one(client: httpx.AsyncClient, pj: str, cid: int, lid: int) -> Optional[Dict[str, Any]]:
        try:
            params = {"project_code": pj, "customer_id": cid, "lot_id": lid}
            r = await client.get("/api/v1/report/bid_tickets/one", headers=headers, params=params)
            if r.status_code != 200:
                return None
            js = r.json() or {}
            row = js.get("data") or None
            if isinstance(row, dict) and row.get("customer_id") and row.get("lot_id"):
                return row
            return None
        except Exception:
            return None

    tickets: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
            tasks = [_fetch_one(client, pj, cid, lid) for (pj, cid, lid) in parsed]
            results = await httpx.AsyncClient()._transport  # never reached; just to avoid linter
    except Exception:
        results = None

    # NOTE: không dùng trick internal transport; thực thi gather đúng cách:
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
            coros = [_fetch_one(client, pj, cid, lid) for (pj, cid, lid) in parsed]
            fetched = await __import__("asyncio").gather(*coros)
            tickets = [x for x in fetched if isinstance(x, dict)]
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not tickets:
        return HTMLResponse("<h1>Không lấy được dữ liệu phiếu để in.</h1>", status_code=404)

    # Sort đúng yêu cầu: lot_id asc, rồi customer_id asc
    tickets.sort(key=lambda t: (t.get("lot_id") or 10**18, t.get("customer_id") or 10**18))

    return templates.TemplateResponse(
        "pages/bid_tickets/print.html",
        {
            "request": request,
            "me": me,
            "tickets": tickets,
        },
    )
