# routers/bid_tickets.py (Service B - Admin)

from __future__ import annotations
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote
import os
import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me
from utils.bid_ticket_issue_client import attach_qr_to_tickets
from utils.document_templates.registry import DocKind, company_code_from_me, resolve_template

router = APIRouter(prefix="/bid-tickets", tags=["bid_tickets"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


def _bid_sheet_template(me: Optional[Dict[str, Any]]) -> str:
    return resolve_template(company_code_from_me(me), DocKind.BID_SHEET)


async def _tickets_with_qr(
    access_token: str,
    tickets: List[Dict[str, Any]],
    *,
    source: str = "PRE_SESSION",
    print_ctx: Optional[Dict[str, Any]] = None,
    default_session_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    return await attach_qr_to_tickets(
        access_token,
        tickets,
        source=source,
        print_ctx=print_ctx,
        default_session_id=default_session_id,
    )


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


def _api_error_message(body: Any, fallback: str = "Lỗi không xác định") -> str:
    if not isinstance(body, dict):
        return fallback
    detail = body.get("detail")
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                msg = item.get("msg") or item.get("message")
                if msg:
                    parts.append(str(msg))
        if parts:
            return "; ".join(parts)
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    err = body.get("error")
    if isinstance(err, str) and err.strip():
        return err.strip()
    return fallback


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


async def _fetch_project_by_code(
    token: str,
    project_code: str,
) -> Optional[Dict[str, Any]]:
    headers = {"Authorization": f"Bearer {token}"}
    code = (project_code or "").strip()
    if not code:
        return None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=15.0) as client:
            st, js = await _get_json(
                client,
                f"/api/v1/projects/by_code/{quote(code)}",
                headers,
                {},
            )
        if st != 200 or not isinstance(js, dict):
            return None
        return js.get("data") or js
    except Exception:
        return None


def _project_lot_assign_context(project: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(project, dict):
        return {
            "show_lot_assign": False,
            "project_id": None,
            "registration_mode": "NORMAL",
            "lot_policy": None,
        }
    reg_mode = (project.get("registration_mode") or "NORMAL").strip().upper()
    ga = project.get("group_auction") if isinstance(project.get("group_auction"), dict) else {}
    lot_policy = (ga.get("lot_policy") or "IN_SESSION_R1").strip().upper()
    is_group = reg_mode == "GROUP_AUCTION"
    return {
        "show_lot_assign": bool(is_group and lot_policy == "PRE_SESSION"),
        "project_id": project.get("id"),
        "registration_mode": reg_mode,
        "lot_policy": lot_policy if is_group else None,
        "lot_policy_label": ga.get("lot_policy_label"),
    }


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
def _summarize_bid_ticket_rows(rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    customer_ids: set[int] = set()
    lot_keys: set[Tuple[str, int]] = set()
    for r in rows:
        cid = r.get("customer_id")
        if cid is not None:
            customer_ids.add(int(cid))
        pj2 = (r.get("project_code") or "").strip()
        lid = r.get("lot_id")
        if pj2 and lid is not None:
            lot_keys.add((pj2, int(lid)))
    return len(customer_ids), len(lot_keys)


def _group_bid_ticket_customers(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
    return customers_list


def _group_bid_ticket_lots(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
    return lots_list


@router.get("", response_class=HTMLResponse)
async def bid_tickets_page(
    request: Request,
    project_code: Optional[str] = Query(None),
    customer_q: Optional[str] = Query(None, description="Tên khách / CCCD / điện thoại"),
    lot_code: Optional[str] = Query(None),
    tab: str = Query("customers", description="customers | lots"),
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

    active_tab = "lots" if (tab or "").strip().lower() == "lots" else "customers"

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
            if active_tab == "lots":
                qs.append("tab=lots")
            if page and page != 1:
                qs.append(f"page={page}")
            return RedirectResponse(url="/bid-tickets?" + "&".join(qs), status_code=303)

        return templates.TemplateResponse(
            "pages/bid_tickets/index.html",
            {
                "request": request,
                "title": "Phiếu trả giá",
                "me": me,
                "active_tab": active_tab,
                "filters": {
                    "project_code": "",
                    "customer_q": customer_q or "",
                    "lot_code": lot_code or "",
                },
                "customers": [],
                "lots": [],
                "lots_total": 0,
                "pairs_total": 0,
                "customers_total": 0,
                "load_err": "Vui lòng chọn dự án trước khi thao tác / in phiếu.",
                **_project_lot_assign_context(None),
            },
        )

    project_meta = await _fetch_project_by_code(token, pj)
    lot_assign_ctx = _project_lot_assign_context(project_meta)

    params: Dict[str, Any] = {
        "page": page,
        "size": size,
        "project_code": pj,
        "include_total": False,
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
    customers_total, lots_total = _summarize_bid_ticket_rows(rows)
    pairs_total = len(rows)

    if active_tab == "lots":
        customers_list: List[Dict[str, Any]] = []
        lots_list = _group_bid_ticket_lots(rows)
    else:
        customers_list = _group_bid_ticket_customers(rows)
        lots_list = []

    return templates.TemplateResponse(
        "pages/bid_tickets/index.html",
        {
            "request": request,
            "title": "Phiếu trả giá",
            "me": me,
            "active_tab": active_tab,
            "filters": {
                "project_code": pj,
                "customer_q": customer_q or "",
                "lot_code": lot_code or "",
            },
            "customers": customers_list,
            "lots": lots_list,
            "lots_total": lots_total,
            "pairs_total": pairs_total,
            "customers_total": customers_total,
            "load_err": load_err,
            **lot_assign_ctx,
        },
    )


@router.get("/lot-assign", response_class=HTMLResponse)
async def lot_assign_page(
    request: Request,
    project_code: Optional[str] = Query(None),
):
    """Màn hình gán lô PRE_SESSION — full page (mục 5.2)."""
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote('/bid-tickets/lot-assign')}",
            status_code=303,
        )

    pj = (project_code or "").strip()
    if not pj:
        picked = await _auto_pick_project_code_if_missing(
            token=token,
            me=me,
            incoming_filters={},
        )
        if picked:
            return RedirectResponse(
                url=f"/bid-tickets/lot-assign?project_code={quote(picked)}",
                status_code=303,
            )

    project_meta = await _fetch_project_by_code(token, pj) if pj else None
    lot_assign_ctx = _project_lot_assign_context(project_meta)

    if pj and not lot_assign_ctx.get("show_lot_assign"):
        return templates.TemplateResponse(
            "pages/bid_tickets/lot_assign.html",
            {
                "request": request,
                "title": "Gán mã lô",
                "me": me,
                "filters": {"project_code": pj},
                "load_err": "Dự án này không dùng chính sách gán lô trước phiên (PRE_SESSION).",
                **lot_assign_ctx,
            },
        )

    return templates.TemplateResponse(
        "pages/bid_tickets/lot_assign.html",
        {
            "request": request,
            "title": "Gán mã lô",
            "me": me,
            "filters": {"project_code": pj},
            "load_err": None if pj else "Vui lòng chọn dự án để gán lô.",
            **lot_assign_ctx,
        },
    )


@router.get("/api/group-deposit-assignments", response_class=JSONResponse)
async def api_group_deposit_assignments(
    request: Request,
    project_code: str = Query(...),
):
    """Proxy: bảng gán lô PRE_SESSION cho mục 5.2."""
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    project = await _fetch_project_by_code(token, project_code)
    ctx = _project_lot_assign_context(project)
    if not ctx.get("show_lot_assign") or not ctx.get("project_id"):
        return JSONResponse(
            {"ok": False, "error": "Dự án không áp dụng gán lô trước phiên (PRE_SESSION)."},
            status_code=400,
        )

    pid = int(ctx["project_id"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
            r = await client.get(
                f"/api/v1/projects/{pid}/group-deposit-assignments",
                headers=headers,
            )
        body = r.json() if r.content else {"ok": False}
        if r.status_code >= 400 and isinstance(body, dict) and not body.get("error"):
            body = {**body, "error": _api_error_message(body, f"HTTP {r.status_code}")}
        return JSONResponse(body, status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.put("/api/group-deposits/{order_id}/assign-lot", response_class=JSONResponse)
async def api_assign_group_deposit_lot_bid_tickets(
    request: Request,
    order_id: int,
    project_code: str = Query(...),
):
    """Proxy: gán lô cho đơn cọc nhóm từ mục 5.2."""
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    project = await _fetch_project_by_code(token, project_code)
    ctx = _project_lot_assign_context(project)
    if not ctx.get("show_lot_assign") or not ctx.get("project_id"):
        return JSONResponse(
            {"ok": False, "error": "Dự án không áp dụng gán lô trước phiên."},
            status_code=400,
        )

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    pid = int(ctx["project_id"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
            r = await client.put(
                f"/api/v1/projects/{pid}/group-deposits/{order_id}/assign-lot",
                headers=headers,
                json=payload,
            )
        body = r.json() if r.content else {"ok": False}
        if r.status_code >= 400:
            msg = _api_error_message(body, "Gán lô thất bại")
            return JSONResponse({"ok": False, "error": msg, "detail": body.get("detail")}, status_code=r.status_code)
        return JSONResponse(body, status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.put("/api/group-deposits/{order_id}/unassign-lot", response_class=JSONResponse)
async def api_unassign_group_deposit_lot_bid_tickets(
    request: Request,
    order_id: int,
    project_code: str = Query(...),
):
    """Proxy: huỷ gán lô đơn cọc nhóm."""
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    project = await _fetch_project_by_code(token, project_code)
    ctx = _project_lot_assign_context(project)
    if not ctx.get("show_lot_assign") or not ctx.get("project_id"):
        return JSONResponse(
            {"ok": False, "error": "Dự án không áp dụng gán lô trước phiên."},
            status_code=400,
        )

    pid = int(ctx["project_id"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
            r = await client.put(
                f"/api/v1/projects/{pid}/group-deposits/{order_id}/unassign-lot",
                headers=headers,
                json={},
            )
        body = r.json() if r.content else {"ok": False}
        if r.status_code >= 400:
            msg = _api_error_message(body, "Huỷ gán lô thất bại")
            return JSONResponse({"ok": False, "error": msg, "detail": body.get("detail")}, status_code=r.status_code)
        return JSONResponse(body, status_code=r.status_code)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


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

    # ✅ FIX: sort theo LOT_ID (không dùng lot_code string)
    rows.sort(
        key=lambda t: (
            t.get("stt") if t.get("stt") is not None else 2147483647,
            t.get("customer_id") if t.get("customer_id") is not None else 10**18,
            t.get("lot_id") if t.get("lot_id") is not None else 10**18,
            t.get("lot_code") or "",
        )
    )

    rows = await _tickets_with_qr(token, rows, source="PRE_SESSION")

    return templates.TemplateResponse(
        _bid_sheet_template(me),
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

    # ✅ FIX: sort theo LOT_ID (không dùng lot_code string)
    rows.sort(
        key=lambda t: (
            t.get("stt") if t.get("stt") is not None else 2147483647,
            t.get("customer_id") if t.get("customer_id") is not None else 10**18,
            t.get("lot_id") if t.get("lot_id") is not None else 10**18,
            t.get("lot_code") or "",
        )
    )

    rows = await _tickets_with_qr(token, rows, source="PRE_SESSION")

    return templates.TemplateResponse(
        _bid_sheet_template(me),
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

    tickets = await _tickets_with_qr(token, tickets, source="PRE_SESSION")

    # Sort đã do A quyết định; B giữ nguyên.
    return templates.TemplateResponse(
        _bid_sheet_template(me),
        {
            "request": request,
            "me": me,
            "tickets": tickets,
        },
    )


# ======================================================================
# NEW: PRINT-TIED (NEXT ROUND)
# - B gọi A lấy pairs đang TIED theo counting session
# - Sau đó gọi A bulk bid_tickets/selected để render PRINT_TEMPLATE
# ======================================================================
from typing import Literal

@router.get("/print-tied", response_class=HTMLResponse)
async def print_tied_bid_tickets_next_round(
    request: Request,
    # ưu tiên nhận session_id trực tiếp (đơn giản nhất)
    session_id: int = Query(..., ge=1, description="auction_counting session_id (COUNTING)"),
    # optional: chỉ in 1 lô (phục vụ nút In của lô trong màn kiểm phiếu)
    only_lot_id: Optional[int] = Query(None, ge=1),
    # NEW: sort_type forward sang Service A
    sort_type: Literal["lot_customer", "customer_lot"] = Query(
        "lot_customer",
        description="Sort output pairs: lot_customer (default) hoặc customer_lot",
    ),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote('/bid-tickets')}",
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}

    # 1) lấy danh sách cặp lot+customer đang TIED từ A
    params_pairs: Dict[str, Any] = {
        "sort_type": sort_type,  # 👈 forward sang A
    }
    if only_lot_id is not None:
        params_pairs["only_lot_id"] = int(only_lot_id)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
            r = await client.get(
                f"/api/v1/auction-counting/print/sessions/{int(session_id)}/tied-print-pairs",
                headers=headers,
                params=params_pairs,
            )
        if r.status_code != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không lấy được danh sách TIED để in (HTTP {r.status_code}).</p>",
                status_code=500,
            )
        js_pairs = r.json() or {}
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    pairs = (js_pairs or {}).get("pairs") or []
    project = (js_pairs or {}).get("project") or {}
    project_code = (project.get("project_code") or "").strip()

    if not project_code:
        return HTMLResponse("<h1>Lỗi</h1><p>Thiếu project_code từ API counting print.</p>", status_code=500)

    if not isinstance(pairs, list) or not pairs:
        return HTMLResponse("<h1>Không có lô nào đang TIED để in.</h1>", status_code=404)

    # normalize pairs => items cho bulk bid_tickets
    items: List[Dict[str, int]] = []
    seen = set()
    for p in pairs:
        if not isinstance(p, dict):
            continue
        lid = p.get("lot_id")
        cid = p.get("customer_id")
        try:
            lid = int(lid)
            cid = int(cid)
        except Exception:
            continue
        if lid <= 0 or cid <= 0:
            continue
        k = (cid, lid)
        if k in seen:
            continue
        seen.add(k)
        items.append({"customer_id": cid, "lot_id": lid})

    if not items:
        return HTMLResponse("<h1>Không có cặp hợp lệ để in.</h1>", status_code=400)

    # 2) gọi bulk selected để lấy dữ liệu phiếu
    payload = {
        "project_code": project_code,
        "items": items,
        "include_excluded": False,
        # giữ nguyên để không phụ thuộc việc A có hỗ trợ sort_mode khác hay không
        "sort_mode": "LOT_ASC_CUSTOMER_ASC",
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=60.0) as client:
            r2 = await client.post("/api/v1/report/bid_tickets/selected", headers=headers, json=payload)
        if r2.status_code != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu để in (HTTP {r2.status_code}).</p>",
                status_code=500,
            )
        js2 = r2.json() or {}
        tickets: List[Dict[str, Any]] = js2.get("data") or []
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not tickets:
        return HTMLResponse("<h1>Không lấy được dữ liệu phiếu để in.</h1>", status_code=404)

    # ✅ FIX CỐT LÕI:
    # /api/v1/report/bid_tickets/selected có thể đã sort lại theo LOT (do sort_mode),
    # nên B phải sort lại lần cuối đúng theo sort_type để đảm bảo thứ tự in.
    if sort_type == "customer_lot":
        tickets.sort(
            key=lambda t: (
                t.get("customer_id") if t.get("customer_id") is not None else 10**18,
                t.get("lot_id") if t.get("lot_id") is not None else 10**18,
                t.get("lot_code") or "",
            )
        )
    else:
        tickets.sort(
            key=lambda t: (
                t.get("lot_id") if t.get("lot_id") is not None else 10**18,
                t.get("customer_id") if t.get("customer_id") is not None else 10**18,
                t.get("lot_code") or "",
            )
        )

    print_ctx = {
        "mode": "TIED_NEXT_ROUND",
        "session_id": int(session_id),
        "only_lot_id": int(only_lot_id) if only_lot_id is not None else None,
        "project_code": project_code,
        "project_name": project.get("project_name"),
        "pairs_count": len(items),
        "sort_type": sort_type,
    }
    tickets = await _tickets_with_qr(
        token,
        tickets,
        source="TIED",
        print_ctx=print_ctx,
        default_session_id=int(session_id),
    )

    return templates.TemplateResponse(
        _bid_sheet_template(me),
        {
            "request": request,
            "me": me,
            "tickets": tickets,
            "print_ctx": print_ctx,
        },
    )

