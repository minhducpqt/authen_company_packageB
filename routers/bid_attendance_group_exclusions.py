# routers/bid_attendance_group_exclusions.py (Service B — đấu nhóm only)
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote
import os

import httpx
from fastapi import APIRouter, Request, Query, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/bid-attendance", tags=["bid_attendance_group"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
GROUP_API = "/api/v1/auction/group-attendance-exclusions"


async def _get_json(client, url, headers, params):
    r = await client.get(url, headers=headers, params=params)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


async def _post_json(client, url, headers, payload, params=None):
    r = await client.post(url, headers=headers, params=params or {}, json=payload)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


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


async def fetch_registration_mode(client: httpx.AsyncClient, headers: dict, project_code: str) -> str:
    st, js = await _get_json(
        client,
        "/api/v1/report/bid_tickets/customers",
        headers,
        {"project_code": project_code, "page": 1, "size": 1},
    )
    if st == 200 and isinstance(js, dict):
        return ((js.get("meta") or {}).get("registration_mode") or "NORMAL").upper()
    return "NORMAL"


async def render_group_detail_page(
    request: Request,
    *,
    project_code: str,
    customer_id: int,
    me: dict,
    err: Optional[str] = None,
    ok: Optional[str] = None,
) -> HTMLResponse:
    token = get_access_token(request)
    headers = {"Authorization": f"Bearer {token}"}

    load_err: Optional[str] = None
    customer: Dict[str, Any] = {}
    deposits: List[Dict[str, Any]] = []
    summary: Optional[Dict[str, Any]] = None
    excluded_order_ids: List[int] = []

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            st_c, js_c = await _get_json(
                client,
                "/api/v1/report/bid_tickets/customers",
                headers,
                {"project_code": project_code, "customer_id": customer_id, "page": 1, "size": 1},
            )
            if st_c == 200 and isinstance(js_c, dict) and (js_c.get("data") or []):
                row = js_c["data"][0]
                customer = {
                    "project_id": row.get("project_id"),
                    "project_code": row.get("project_code") or project_code,
                    "project_name": row.get("project_name"),
                    "customer_id": row.get("customer_id") or customer_id,
                    "customer_full_name": row.get("customer_full_name"),
                    "cccd": row.get("cccd"),
                    "phone": row.get("phone"),
                    "email": row.get("email"),
                    "address": row.get("address"),
                    "stt": row.get("stt"),
                    "stt_padded": row.get("stt_padded"),
                    "customer_group_count": row.get("customer_group_count"),
                    "customer_lot_count": row.get("customer_lot_count"),
                    "total_deposit_amount": row.get("total_deposit_amount"),
                }
            else:
                load_err = "Không tìm thấy khách trong danh sách điểm danh đấu nhóm."

            pid = customer.get("project_id")
            if pid and not load_err:
                st_s, js_s = await _get_json(
                    client,
                    f"{GROUP_API}/summary",
                    headers,
                    {"project_id": int(pid), "customer_id": int(customer_id)},
                )
                if st_s == 200 and isinstance(js_s, dict):
                    summary = js_s.get("data")

                st_d, js_d = await _get_json(
                    client,
                    f"{GROUP_API}/auto-deposits",
                    headers,
                    {"project_id": int(pid), "customer_id": int(customer_id)},
                )
                if st_d == 200 and isinstance(js_d, dict):
                    data = js_d.get("data") or {}
                    deposits = data.get("deposits") or []
                    if data.get("customer"):
                        for k, v in data["customer"].items():
                            if customer.get(k) in (None, "", []):
                                customer[k] = v
                elif not deposits:
                    load_err = load_err or f"Không tải được giao dịch cọc (HTTP {st_d})."

    except Exception as e:
        load_err = str(e)

    if isinstance(summary, dict):
        for oid in summary.get("excluded_order_ids") or []:
            try:
                excluded_order_ids.append(int(oid))
            except Exception:
                pass
        if summary.get("is_customer_fully_excluded"):
            excluded_order_ids = [int(d.get("order_id")) for d in deposits if d.get("order_id") is not None]

    excluded_order_ids = sorted(set(excluded_order_ids))

    return templates.TemplateResponse(
        "pages/bid_attendance/detail_group.html",
        {
            "request": request,
            "title": "Chi tiết điểm danh (đấu nhóm)",
            "me": me,
            "load_err": load_err,
            "err": err,
            "ok": ok,
            "project_code": project_code,
            "customer_id": customer_id,
            "customer": customer,
            "deposits": deposits,
            "summary": summary,
            "excluded_order_ids": excluded_order_ids,
        },
    )


@router.post("/detail/group/exclude-customer")
async def group_exclude_customer_action(
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
    if (confirm_text or "").strip().lower() != "tôi xác nhận":
        return _redirect_err(project_code, customer_id, _CONFIRM_MSG)
    reason = (reason or "").strip()
    if not reason:
        return _redirect_err(project_code, customer_id, _REASON_REQUIRED_MSG)

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            st, _ = await _post_json(
                client,
                f"{GROUP_API}/exclude-customer",
                headers,
                {"project_id": int(project_id), "customer_id": int(customer_id), "reason": reason},
            )
        if st != 200:
            return HTMLResponse(f"<h1>Lỗi</h1><p>Không loại được khách (HTTP {st}).</p>", status_code=500)
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    return _redirect_ok(project_code, customer_id, "Đã loại khách khỏi danh sách điểm danh (full).")


@router.post("/detail/group/clear-customer")
async def group_clear_customer_action(
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

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            st, _ = await _post_json(
                client,
                f"{GROUP_API}/clear-customer",
                headers,
                {"project_id": int(project_id), "customer_id": int(customer_id)},
            )
        if st != 200:
            return HTMLResponse(f"<h1>Lỗi</h1><p>Không gỡ loại khách (HTTP {st}).</p>", status_code=500)
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    return _redirect_ok(project_code, customer_id, "Đã gỡ loại khách (mở lại toàn bộ giao dịch cọc).")


@router.post("/detail/group/exclude-order")
async def group_exclude_order_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    order_id: int = Form(...),
    reason: str = Form(...),
    confirm_text: str = Form(""),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return _redirect_login(project_code, customer_id)
    if (confirm_text or "").strip().lower() != "tôi xác nhận":
        return _redirect_err(project_code, customer_id, _CONFIRM_MSG)
    reason = (reason or "").strip()
    if not reason:
        return _redirect_err(project_code, customer_id, _REASON_REQUIRED_MSG)

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            st, _ = await _post_json(
                client,
                f"{GROUP_API}/exclude-order",
                headers,
                {
                    "project_id": int(project_id),
                    "customer_id": int(customer_id),
                    "order_id": int(order_id),
                    "reason": reason,
                },
            )
        if st != 200:
            return HTMLResponse(f"<h1>Lỗi</h1><p>Không loại được giao dịch cọc (HTTP {st}).</p>", status_code=500)
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    return _redirect_ok(project_code, customer_id, f"Đã loại giao dịch cọc order_id={order_id}.")


@router.post("/detail/group/clear-order")
async def group_clear_order_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    order_id: int = Form(...),
    confirm_text: str = Form(""),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return _redirect_login(project_code, customer_id)
    if (confirm_text or "").strip().lower() != "tôi xác nhận":
        return _redirect_err(project_code, customer_id, _CONFIRM_MSG)

    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=25.0) as client:
            st, _ = await _post_json(
                client,
                f"{GROUP_API}/clear-order",
                headers,
                {
                    "project_id": int(project_id),
                    "customer_id": int(customer_id),
                    "order_id": int(order_id),
                },
            )
        if st != 200:
            return HTMLResponse(f"<h1>Lỗi</h1><p>Không gỡ loại giao dịch (HTTP {st}).</p>", status_code=500)
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    return _redirect_ok(project_code, customer_id, f"Đã gỡ loại giao dịch cọc order_id={order_id}.")
