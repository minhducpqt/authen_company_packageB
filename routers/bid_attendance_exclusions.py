# routers/bid_attendance_exclusions.py (Service B - Admin)
from __future__ import annotations

from typing import Optional, Dict, Any, List
from urllib.parse import quote
import os

import httpx
from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/bid-attendance", tags=["bid_attendance"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# =========================================================
# HTTP helpers
# =========================================================
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


async def _post_json(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    payload: dict,
    params: Optional[dict] = None,
):
    r = await client.post(url, headers=headers, params=params or {}, json=payload)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        return None


def _redirect_login(project_code: str, customer_id: int):
    next_url = f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}"
    return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)


def _redirect_err(project_code: str, customer_id: int, msg: str):
    return RedirectResponse(
        url=(
            f"/bid-attendance/detail?project_code={quote(project_code)}"
            f"&customer_id={customer_id}&err={quote(msg)}"
        ),
        status_code=303,
    )


def _redirect_ok(project_code: str, customer_id: int, msg: str):
    return RedirectResponse(
        url=(
            f"/bid-attendance/detail?project_code={quote(project_code)}"
            f"&customer_id={customer_id}&ok={quote(msg)}"
        ),
        status_code=303,
    )


_CONFIRM_MSG = 'Vui lòng nhập đúng cụm "tôi xác nhận" để thực hiện thao tác.'
_REASON_REQUIRED_MSG = "Vui lòng nhập lý do loại (bắt buộc)."


# =========================================================
# DETAIL PAGE: 1 KHÁCH trong 1 DỰ ÁN (để Loại/Gỡ theo LOT hoặc theo CUSTOMER)
# - Nguồn dữ liệu:
#   1) /api/v1/report/bid_tickets?project_code&customer_id -> info KH + list lots
#   2) /api/v1/auction/eligibility-exclusions/summary?project_id&customer_id -> trạng thái loại theo lot
# =========================================================
@router.get("/detail", response_class=HTMLResponse)
async def bid_attendance_detail_page(
    request: Request,
    project_code: str = Query(...),
    customer_id: int = Query(...),
    err: Optional[str] = Query(None),
    ok: Optional[str] = Query(None),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return _redirect_login(project_code, customer_id)

    headers = {"Authorization": f"Bearer {token}"}

    load_err: Optional[str] = None
    customer: Dict[str, Any] = {}
    lots: List[Dict[str, Any]] = []
    summary: Optional[Dict[str, Any]] = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            # 1) Lấy dữ liệu khách + các lô tham gia (tận dụng report bid_tickets)
            params = {
                "project_code": project_code,
                "customer_id": customer_id,
                "page": 1,
                "size": 2000,
            }
            st, js = await _get_json(client, "/api/v1/report/bid_tickets", headers, params)
            if st != 200 or not isinstance(js, dict):
                load_err = f"Không tải được dữ liệu điểm danh (HTTP {st})."
            else:
                rows = js.get("data") or []
                if not rows:
                    load_err = "Không tìm thấy khách trong danh sách đủ điều kiện (hoặc đã bị thay đổi dữ liệu)."
                else:
                    r0 = rows[0]
                    customer = {
                        "company_code": r0.get("company_code"),
                        "company_name": r0.get("company_name"),
                        "project_id": r0.get("project_id"),
                        "project_code": r0.get("project_code"),
                        "project_name": r0.get("project_name"),
                        "auction_mode": r0.get("auction_mode"),
                        "customer_id": r0.get("customer_id"),
                        "customer_full_name": r0.get("customer_full_name"),
                        "cccd": r0.get("cccd"),
                        "phone": r0.get("phone"),
                        "email": r0.get("email"),
                        "address": r0.get("address"),
                        "dob": r0.get("dob"),
                        "stt": r0.get("stt"),
                        "stt_padded": r0.get("stt_padded"),
                        "customer_lot_count": r0.get("customer_lot_count"),
                        "total_deposit_amount_per_customer_project": r0.get(
                            "total_deposit_amount_per_customer_project"
                        ),
                    }
                    lots = rows

            # 2) Summary trạng thái loại theo lô (nếu có project_id)
            pid = _safe_int(customer.get("project_id"))
            if pid:
                st2, js2 = await _get_json(
                    client,
                    "/api/v1/auction/eligibility-exclusions/summary",
                    headers,
                    {"project_id": pid, "customer_id": int(customer_id)},
                )
                if st2 == 200 and isinstance(js2, dict):
                    summary = js2.get("data")
                else:
                    summary = None

    except Exception as e:
        load_err = str(e)

    # Map excluded_lot_ids for template render
    excluded_lot_ids: List[int] = []
    if isinstance(summary, dict):
        for lid in (summary.get("excluded_lot_ids") or []):
            try:
                excluded_lot_ids.append(int(lid))
            except Exception:
                pass

    return templates.TemplateResponse(
        "pages/bid_attendance/detail.html",
        {
            "request": request,
            "title": "Chi tiết điểm danh",
            "me": me,
            "load_err": load_err,
            "err": err,
            "ok": ok,
            "project_code": project_code,
            "customer_id": customer_id,
            "customer": customer,
            "lots": lots,
            "summary": summary,
            "excluded_lot_ids": sorted(list(set(excluded_lot_ids))),
        },
    )


# =========================================================
# ACTION: EXCLUDE CUSTOMER (Loại khách = loại tất cả lô hợp lệ)
# - POST Service A: /api/v1/auction/eligibility-exclusions/exclude-customer
# =========================================================
@router.post("/detail/exclude-customer")
async def bid_attendance_exclude_customer_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    reason: str = Form(...),
    confirm_text: str = Form(""),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return _redirect_login(project_code, customer_id)

    # enforce confirm text
    if (confirm_text or "").strip().lower() != "tôi xác nhận":
        return _redirect_err(project_code, customer_id, _CONFIRM_MSG)

    payload = {
        "project_id": int(project_id),
        "customer_id": int(customer_id),
        "reason": (reason or "").strip(),
    }
    if not payload["reason"]:
        return _redirect_err(project_code, customer_id, _REASON_REQUIRED_MSG)

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            st, js = await _post_json(
                client,
                "/api/v1/auction/eligibility-exclusions/exclude-customer",
                headers,
                payload,
            )
        if st != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không loại được khách (HTTP {st}).</p><pre>{js}</pre>",
                status_code=500,
            )
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    msg = "Đã loại khách (loại toàn bộ lô hợp lệ)."
    return _redirect_ok(project_code, customer_id, msg)


# =========================================================
# ACTION: CLEAR CUSTOMER (Gỡ loại khách = gỡ loại tất cả lô)
# - POST Service A: /api/v1/auction/eligibility-exclusions/clear-customer
# =========================================================
@router.post("/detail/clear-customer")
async def bid_attendance_clear_customer_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    confirm_text: str = Form(""),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return _redirect_login(project_code, customer_id)

    if (confirm_text or "").strip().lower() != "tôi xác nhận":
        return _redirect_err(project_code, customer_id, _CONFIRM_MSG)

    payload = {"project_id": int(project_id), "customer_id": int(customer_id)}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            st, js = await _post_json(
                client,
                "/api/v1/auction/eligibility-exclusions/clear-customer",
                headers,
                payload,
            )
        if st != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không gỡ loại khách (HTTP {st}).</p><pre>{js}</pre>",
                status_code=500,
            )
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    msg = "Đã gỡ loại khách (gỡ loại tất cả lô)."
    return _redirect_ok(project_code, customer_id, msg)


# =========================================================
# ACTION: EXCLUDE ONE LOT
# - POST Service A: /api/v1/auction/eligibility-exclusions/exclude-lot
# =========================================================
@router.post("/detail/exclude-lot")
async def bid_attendance_exclude_lot_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    lot_id: int = Form(...),
    reason: str = Form(...),
    confirm_text: str = Form(""),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return _redirect_login(project_code, customer_id)

    if (confirm_text or "").strip().lower() != "tôi xác nhận":
        return _redirect_err(project_code, customer_id, _CONFIRM_MSG)

    payload = {
        "project_id": int(project_id),
        "customer_id": int(customer_id),
        "lot_id": int(lot_id),
        "reason": (reason or "").strip(),
    }
    if not payload["reason"]:
        return _redirect_err(project_code, customer_id, _REASON_REQUIRED_MSG)

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            st, js = await _post_json(
                client,
                "/api/v1/auction/eligibility-exclusions/exclude-lot",
                headers,
                payload,
            )
        if st != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không loại được lô (HTTP {st}).</p><pre>{js}</pre>",
                status_code=500,
            )
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    msg = f"Đã loại lô ID={lot_id}."
    return _redirect_ok(project_code, customer_id, msg)


# =========================================================
# ACTION: CLEAR ONE LOT
# - POST Service A: /api/v1/auction/eligibility-exclusions/clear-lot
# =========================================================
@router.post("/detail/clear-lot")
async def bid_attendance_clear_lot_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    lot_id: int = Form(...),
    confirm_text: str = Form(""),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return _redirect_login(project_code, customer_id)

    if (confirm_text or "").strip().lower() != "tôi xác nhận":
        return _redirect_err(project_code, customer_id, _CONFIRM_MSG)

    payload = {"project_id": int(project_id), "customer_id": int(customer_id), "lot_id": int(lot_id)}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            st, js = await _post_json(
                client,
                "/api/v1/auction/eligibility-exclusions/clear-lot",
                headers,
                payload,
            )
        if st != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không gỡ loại được lô (HTTP {st}).</p><pre>{js}</pre>",
                status_code=500,
            )
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    msg = f"Đã gỡ loại lô ID={lot_id}."
    return _redirect_ok(project_code, customer_id, msg)
