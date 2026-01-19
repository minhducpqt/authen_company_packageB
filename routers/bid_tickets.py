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


async def _auto_pick_project_code_if_missing(
    token: str,
    me: dict,
    incoming_filters: dict,
) -> Optional[str]:
    """
    Nếu chưa chọn project_code:
      - Nếu có đúng 1 ACTIVE -> chọn nó
      - Nếu có nhiều ACTIVE -> chọn ACTIVE ở cuối danh sách
    Trả về project_code hoặc None nếu không chọn được.
    """
    headers = {"Authorization": f"Bearer {token}"}
    company_code = (me or {}).get("company_code") or (me or {}).get("company") or (me or {}).get("companyCode")
    company_code = (company_code or "").strip()

    params = {
        "status": "ACTIVE",
        "page": 1,
        "size": 1000,
    }
    if company_code:
        params["company_code"] = company_code

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=15.0) as client:
            st, js = await _get_json(client, "/api/v1/projects/public", headers, params)
        if st != 200 or not isinstance(js, dict):
            return None
        items = js.get("data") or js.get("items") or []
        if not isinstance(items, list):
            return None
        items = [x for x in items if isinstance(x, dict)]
        if not items:
            return None
        if len(items) == 1:
            return (items[0].get("project_code") or "").strip() or None
        last = items[-1]
        return (last.get("project_code") or "").strip() or None
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
    - BẮT BUỘC có project_code mới tải dữ liệu (chống trộn dự án).
    - Nếu chưa có project_code:
        + auto chọn nếu có 1 ACTIVE hoặc chọn ACTIVE cuối danh sách
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

    pj = (project_code or "").strip()

    if not pj:
        picked = await _auto_pick_project_code_if_missing(
            token=token,
            me=me,
            incoming_filters={
                "customer_q": customer_q or "",
                "lot_code": lot_code or "",
                "page": page,
                "size": size,
            },
        )
        if picked:
            qs = [f"project_code={quote(picked)}"]
            if customer_q:
                qs.append(f"customer_q={quote(customer_q)}")
            if lot_code:
                qs.append(f"lot_code={quote(lot_code)}")
            if page and page != 1:
                qs.append(f"page={page}")
            if size:
                qs.append(f"size={size}")
            return RedirectResponse(url="/bid-tickets?" + "&".join(qs), status_code=303)

        return templates.TemplateResponse(
            "pages/bid_tickets/index.html",
            {
                "request": request,
                "title": "Phiếu trả giá",
                "me": me,
                "filters": {
                    "project_code": "",
                    "customer_q": customer_q or "",
                    "lot_code": lot_code or "",
                },
                "page": {"data": [], "page": 1, "size": size, "total": 0},
                "rows": [],
                "customers": [],
                "lots": [],
                "lots_total": 0,
                "pairs_total": 0,
                "load_err": "Vui lòng chọn dự án trước khi thao tác / in phiếu.",
            },
        )

    params: Dict[str, Any] = {
        "page": page,
        "size": size,
        "project_code": pj,
    }
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

    # TAB 1: group theo khách
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

    # TAB 2: group theo lô
    lots_map: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for r in rows:
        pj2 = (r.get("project_code") or "").strip()
        lid = r.get("lot_id")
        if not pj2 or lid is None:
            continue
        lid = int(lid)
        key = (pj2, lid)
        if key not in lots_map:
            lots_map[key] = {
                "project_code": pj2,
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
                "project_code": pj,
                "customer_q": customer_q or "",
                "lot_code": lot_code or "",
            },
            "page": data,
            "rows": rows,
            "customers": customers_list,
            "lots": lots_list,
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
# - DÙNG API BULK BÊN A: POST /api/v1/report/bid_tickets/selected
# - only_lot_id: để nút "In của lô" chỉ in những phiếu đã tick thuộc lô đó
# ======================================================================
@router.get("/print-selected", response_class=HTMLResponse)
async def print_selected_bid_tickets(
    request: Request,
    item: List[str] = Query(..., description="Repeated: project|customer_id|lot_id"),
    only_lot_id: Optional[int] = Query(
        None,
        description="Nếu set, chỉ in các item thuộc lot_id này (phục vụ nút In của lô).",
    ),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote('/bid-tickets')}",
            status_code=303,
        )

    # Parse + dedupe
    parsed: List[Tuple[str, int, int]] = []
    seen = set()
    for s in item or []:
        tup = _parse_item(s)
        if not tup:
            continue
        if only_lot_id is not None and tup[2] != int(only_lot_id):
            continue
        if tup in seen:
            continue
        seen.add(tup)
        parsed.append(tup)

    if not parsed:
        return HTMLResponse("<h1>Không có phiếu hợp lệ để in.</h1>", status_code=400)

    # Must be 1 project_code (vì UI bắt chọn dự án trước)
    project_code = (parsed[0][0] or "").strip()
    if not project_code:
        return HTMLResponse("<h1>Thiếu project_code.</h1>", status_code=400)

    # Nếu lẫn project_code (do UI/bug), vẫn chặn để tránh trộn dự án khi in
    for (pj, _, _) in parsed:
        if (pj or "").strip() != project_code:
            return HTMLResponse(
                "<h1>Lỗi</h1><p>Danh sách in bị trộn nhiều dự án. Vui lòng chọn 1 dự án duy nhất.</p>",
                status_code=400,
            )

    # Build payload for Service A bulk endpoint
    payload = {
        "project_code": project_code,
        "items": [{"customer_id": cid, "lot_id": lid} for (_, cid, lid) in parsed],
        "include_excluded": False,
        "sort_mode": "LOT_ASC_CUSTOMER_ASC",
    }

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
            r = await client.post("/api/v1/report/bid_tickets/selected", headers=headers, json=payload)
        if r.status_code != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu để in (HTTP {r.status_code}).</p>",
                status_code=500,
            )
        js = r.json() or {}
        tickets: List[Dict[str, Any]] = js.get("data") or []
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not tickets:
        return HTMLResponse("<h1>Không lấy được dữ liệu phiếu để in.</h1>", status_code=404)

    # Sort đã do A quyết định; B giữ nguyên.
    return templates.TemplateResponse(
        "pages/bid_tickets/print.html",
        {
            "request": request,
            "me": me,
            "tickets": tickets,
        },
    )
