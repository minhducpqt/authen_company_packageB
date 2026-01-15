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
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


# =========================================================
# DETAIL PAGE: 1 KHÁCH trong 1 DỰ ÁN (Loại theo LÔ / Loại tất cả lô)
#
# Nguồn dữ liệu:
#   + /api/v1/report/bid_tickets (lọc theo project_code + customer_id) -> lấy info KH + lots auto đủ đk
#   + /api/v1/auction/eligibility-exclusions/summary (project_id + customer_id) -> excluded lots + remaining
# =========================================================
@router.get("/detail", response_class=HTMLResponse)
async def bid_attendance_detail_page(
    request: Request,
    project_code: str = Query(...),
    customer_id: int = Query(...),
    err: Optional[str] = Query(None),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        next_url = f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}"
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)

    headers = {"Authorization": f"Bearer {token}"}

    load_err: Optional[str] = None
    customer: Dict[str, Any] = {}
    lots: List[Dict[str, Any]] = []
    summary: Optional[Dict[str, Any]] = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
            # 1) Lấy dữ liệu khách + các lô tham gia (auto đủ điều kiện)
            params = {
                "project_code": project_code,
                "customer_id": customer_id,
                "page": 1,
                "size": 5000,
            }
            st, js = await _get_json(client, "/api/v1/report/bid_tickets", headers, params)
            if st != 200 or not isinstance(js, dict):
                load_err = f"Không tải được dữ liệu điểm danh (HTTP {st})."
            else:
                rows = js.get("data") or []
                if not rows:
                    load_err = "Không tìm thấy khách trong danh sách đủ điều kiện (hoặc dữ liệu đã thay đổi)."
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

            # 2) Summary exclusions theo lot (cần project_id)
            pid = _safe_int(customer.get("project_id"))
            if pid:
                st2, js2 = await _get_json(
                    client,
                    "/api/v1/auction/eligibility-exclusions/summary",
                    headers,
                    {"project_id": pid, "customer_id": customer_id},
                )
                if st2 == 200 and isinstance(js2, dict):
                    summary = js2.get("data")
                else:
                    # không coi là lỗi cứng
                    summary = None

    except Exception as e:
        load_err = str(e)

    # Normalize excluded lot ids for UI use
    excluded_ids: List[int] = []
    remaining_ids: List[int] = []
    is_customer_excluded = False
    if isinstance(summary, dict):
        excluded_ids = [int(x) for x in (summary.get("excluded_lot_ids") or []) if _safe_int(x) is not None]
        remaining_ids = [int(x) for x in (summary.get("remaining_lot_ids") or []) if _safe_int(x) is not None]
        is_customer_excluded = bool(summary.get("is_customer_excluded"))

    return templates.TemplateResponse(
        "pages/bid_attendance/detail.html",
        {
            "request": request,
            "title": "Chi tiết điểm danh",
            "me": me,
            "load_err": load_err,
            "flash_err": err,
            "project_code": project_code,
            "customer_id": customer_id,
            "customer": customer,
            "lots": lots,  # list auto đủ đk (trước exclusions)
            "summary": summary,
            "excluded_lot_ids": set(excluded_ids),
            "remaining_lot_ids": set(remaining_ids),
            "is_customer_excluded": is_customer_excluded,
        },
    )


# =========================================================
# ACTION: EXCLUDE 1 LOT
# - Service A: POST /api/v1/auction/eligibility-exclusions/exclude-lot
# =========================================================
@router.post("/detail/exclude-lot")
async def bid_attendance_exclude_lot_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    lot_id: int = Form(...),
    reason: str = Form(...),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        next_url = f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}"
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)

    r_reason = (reason or "").strip()
    if not r_reason:
        return RedirectResponse(
            url=(
                f"/bid-attendance/detail?project_code={quote(project_code)}"
                f"&customer_id={customer_id}&err={quote('Vui lòng nhập lý do loại lô')}"
            ),
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "project_id": int(project_id),
        "customer_id": int(customer_id),
        "lot_id": int(lot_id),
        "reason": r_reason,
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
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

    return RedirectResponse(
        url=f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}",
        status_code=303,
    )


# =========================================================
# ACTION: CLEAR 1 LOT
# - Service A: POST /api/v1/auction/eligibility-exclusions/clear-lot
# =========================================================
@router.post("/detail/clear-lot")
async def bid_attendance_clear_lot_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    lot_id: int = Form(...),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        next_url = f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}"
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "project_id": int(project_id),
        "customer_id": int(customer_id),
        "lot_id": int(lot_id),
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
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

    return RedirectResponse(
        url=f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}",
        status_code=303,
    )


# =========================================================
# ACTION: EXCLUDE CUSTOMER (loại tất cả lô của khách)
# - Service A: POST /api/v1/auction/eligibility-exclusions/exclude-customer
# =========================================================
@router.post("/detail/exclude-customer")
async def bid_attendance_exclude_customer_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    reason: str = Form(...),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        next_url = f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}"
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)

    r_reason = (reason or "").strip()
    if not r_reason:
        return RedirectResponse(
            url=(
                f"/bid-attendance/detail?project_code={quote(project_code)}"
                f"&customer_id={customer_id}&err={quote('Vui lòng nhập lý do loại khách')}"
            ),
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "project_id": int(project_id),
        "customer_id": int(customer_id),
        "reason": r_reason,
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
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

    return RedirectResponse(
        url=f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}",
        status_code=303,
    )


# =========================================================
# ACTION: CLEAR CUSTOMER (gỡ loại tất cả lô của khách)
# - Service A: POST /api/v1/auction/eligibility-exclusions/clear-customer
# =========================================================
@router.post("/detail/clear-customer")
async def bid_attendance_clear_customer_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        next_url = f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}"
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "project_id": int(project_id),
        "customer_id": int(customer_id),
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
            st, js = await _post_json(
                client,
                "/api/v1/auction/eligibility-exclusions/clear-customer",
                headers,
                payload,
            )
        if st != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không gỡ loại được khách (HTTP {st}).</p><pre>{js}</pre>",
                status_code=500,
            )
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    return RedirectResponse(
        url=f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}",
        status_code=303,
    )
