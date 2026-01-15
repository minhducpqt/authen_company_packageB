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


def _detail_url(project_code: str, customer_id: int, err: Optional[str] = None) -> str:
    base = f"/bid-attendance/detail?project_code={quote(project_code)}&customer_id={customer_id}"
    if err:
        base += f"&err={quote(err)}"
    return base


# =========================================================
# DETAIL PAGE: 1 KHÁCH trong 1 DỰ ÁN (để Loại/Gỡ)
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
        next_url = _detail_url(project_code, customer_id)
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)

    headers = {"Authorization": f"Bearer {token}"}

    load_err: Optional[str] = None
    customer: Dict[str, Any] = {}
    lots: List[Dict[str, Any]] = []
    exclusion: Optional[Dict[str, Any]] = None

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

            if st == 401 or st == 403:
                load_err = "Bạn không có quyền hoặc phiên đăng nhập đã hết hạn (Service A)."
            elif st != 200 or not isinstance(js, dict):
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

            # 2) Lấy trạng thái exclusion (nếu đã có project_id)
            if customer.get("project_id"):
                st2, js2 = await _get_json(
                    client,
                    "/api/v1/auction/eligibility-exclusions/one",
                    headers,
                    {"project_id": customer["project_id"], "customer_id": customer_id},
                )
                if st2 == 200 and isinstance(js2, dict):
                    exclusion = js2.get("data")

    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/bid_attendance/detail.html",
        {
            "request": request,
            "title": "Chi tiết điểm danh",
            "me": me,
            "err": err,  # ✅ để show thông báo validate/flow
            "load_err": load_err,
            "project_code": project_code,
            "customer_id": customer_id,
            "customer": customer,
            "lots": lots,
            "exclusion": exclusion,
        },
    )


# =========================================================
# ACTION: EXCLUDE (Loại khách khỏi DS điểm danh)
# =========================================================
@router.post("/detail/exclude")
async def bid_attendance_exclude_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
    reason: str = Form(...),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        next_url = _detail_url(project_code, customer_id)
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)

    reason = (reason or "").strip()
    if not reason:
        return RedirectResponse(
            url=_detail_url(project_code, customer_id, "Vui lòng nhập lý do loại"),
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}
    payload = {"project_id": project_id, "customer_id": customer_id, "reason": reason}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
            st, js = await _post_json(
                client,
                "/api/v1/auction/eligibility-exclusions/exclude",
                headers,
                payload,
            )

        if st == 401 or st == 403:
            return HTMLResponse(
                "<h1>Lỗi</h1><p>Không có quyền thao tác hoặc phiên đăng nhập đã hết hạn (Service A).</p>",
                status_code=403,
            )
        if st != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không loại được khách (HTTP {st}).</p><pre>{js}</pre>",
                status_code=500,
            )

    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    # ✅ Flow hợp lý: loại xong quay về LIST của dự án (người đó sẽ biến mất nếu list có trừ exclusions)
    return RedirectResponse(
        url=f"/bid-attendance?project_code={quote(project_code)}",
        status_code=303,
    )


# =========================================================
# ACTION: CLEAR (Gỡ loại)
# =========================================================
@router.post("/detail/clear")
async def bid_attendance_clear_action(
    request: Request,
    project_id: int = Form(...),
    project_code: str = Form(...),
    customer_id: int = Form(...),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        next_url = _detail_url(project_code, customer_id)
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {"project_id": project_id, "customer_id": customer_id}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
            st, js = await _post_json(
                client,
                "/api/v1/auction/eligibility-exclusions/clear",
                headers,
                payload,
            )

        if st == 401 or st == 403:
            return HTMLResponse(
                "<h1>Lỗi</h1><p>Không có quyền thao tác hoặc phiên đăng nhập đã hết hạn (Service A).</p>",
                status_code=403,
            )
        if st != 200:
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không gỡ loại được khách (HTTP {st}).</p><pre>{js}</pre>",
                status_code=500,
            )

    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    # gỡ loại thì quay lại detail để thấy badge đổi ngay
    return RedirectResponse(
        url=_detail_url(project_code, customer_id),
        status_code=303,
    )
