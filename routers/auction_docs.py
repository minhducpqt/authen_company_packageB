# routers/auction_docs.py
from __future__ import annotations

import os
import datetime
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    Response,
    RedirectResponse,
)

from utils.auth import get_access_token  # dùng giống các router khác của B
from utils.templates import templates
from utils.bid_ticket_qr import qr_png_data_uri
from utils.registration_form_issue_client import issue_registration_form_qr
from utils.document_templates.registry import extract_company_code, resolve_registration_template

# Trùng convention cũ
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


async def _call_service_a_for_registration(
    access_token: str,
    *,
    project_code: str,
    cccd: str,
) -> Dict[str, Any]:
    """
    Gọi Service A để lấy payload ComposeDocResponse.
    Trả về dict: {"code": status_code, "data": <json hoặc None>, "raw": resp}
    """
    params = {
        "project_code": project_code,
        "cccd": cccd,
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
        resp = await client.get(
            "/api/v1/business/documents/auction/registration",
            params=params,
            headers=headers,
        )

    try:
        data = resp.json()
    except Exception:
        data = None

    return {"code": resp.status_code, "data": data, "raw": resp}


# ---------------------------------------------------------------------
# 1) VIEW HTML: dùng cho iframe + in PDF
# ---------------------------------------------------------------------
@router.get("/auction/registration", response_class=HTMLResponse)
async def view_auction_registration(
    request: Request,
    project_code: str = Query(..., description="Mã dự án"),
    cccd: str = Query(..., description="CCCD/CMND khách"),
    download: Optional[str] = Query(
        None,
        description="html -> tải file HTML; để trống -> hiển thị",
    ),
):
    """
    WebAdmin (Service B) gọi endpoint này để:
      - Gọi Service A lấy JSON ComposeDocResponse
      - Render template HTML 'Đơn đăng ký tham gia đấu giá'
      - Hiển thị trong iframe (view) hoặc tải file HTML (download=html)
    """
    access_token = get_access_token(request)
    if not access_token:
        # Chưa đăng nhập => chuyển về login
        return RedirectResponse(
            url="/login?next=%2Fdocuments%2Fauction%2Fregistration",
            status_code=303,
        )

    try:
        upstream = await _call_service_a_for_registration(
            access_token,
            project_code=project_code,
            cccd=cccd,
        )
    except httpx.RequestError as e:
        # Không kết nối được tới A
        return HTMLResponse(
            "<h3>Lỗi kết nối tới Service A.</h3>",
            status_code=502,
        )
    except Exception:
        # Lỗi bất ngờ khi call A
        return HTMLResponse(
            "<h3>Lỗi nội bộ khi gọi Service A.</h3>",
            status_code=500,
        )

    code = int(upstream.get("code", 500))
    data = upstream.get("data") or {}

    # Xử lý mã lỗi từ A
    if code == 401:
        return RedirectResponse(url="/login", status_code=303)
    if code == 404:
        return HTMLResponse(
            "<h3>Không tìm thấy dữ liệu (khách/lô chưa đủ điều kiện).</h3>",
            status_code=404,
        )
    if code >= 500 or not isinstance(data, dict):
        return HTMLResponse(
            "<h3>Lỗi upstream (Service A).</h3>",
            status_code=502,
        )

    # Render HTML từ template in A4
    today = datetime.date.today()

    registration_qr_data_uri = None
    try:
        customer = data.get("customer") or {}
        project = data.get("project") or {}
        project_id = project.get("id")
        customer_id = customer.get("id")
        if project_id is not None and customer_id is not None:
            jti = await issue_registration_form_qr(
                access_token,
                project_id=int(project_id),
                customer_id=int(customer_id),
                source="DEPOSITS_PAGE",
            )
            if jti:
                registration_qr_data_uri = qr_png_data_uri(jti, box_size=6)
    except Exception:
        registration_qr_data_uri = None

    company = data.get("company") or {}
    project = data.get("project") or {}
    registration_mode = (
        project.get("registration_mode")
        or data.get("registration_mode")
        or "NORMAL"
    )
    lot_policy = (
        project.get("lot_policy")
        or (data.get("meta") or {}).get("lot_policy")
        or "IN_SESSION_R1"
    )
    reg_tpl = resolve_registration_template(
        extract_company_code(company=company),
        registration_mode,
        lot_policy=lot_policy,
    )

    html = templates.get_template(reg_tpl).render(
        request=request,
        title="Đơn đăng ký tham gia đấu giá",
        data=data,        # chính là ComposeDocResponse từ A
        today=today,
        year=today.year,
        registration_qr_data_uri=registration_qr_data_uri,
    )

    # Nếu download=html -> trả file .html đính kèm
    if download == "html":
        company_code = (data.get("company") or {}).get("company_code", "COMPANY")
        filename = f"{company_code}_{cccd}_{project_code}.html"
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Mặc định: trả HTML để iframe hiển thị/in PDF
    return HTMLResponse(html)


# ---------------------------------------------------------------------
# 2) (Tùy chọn) endpoint trả JSON thô cho debug / tools
# ---------------------------------------------------------------------
@router.get("/auction/registration/data", response_class=JSONResponse)
async def get_auction_registration_data(
    request: Request,
    project_code: str = Query(..., description="Mã dự án"),
    cccd: str = Query(..., description="CCCD/CMND khách"),
):
    """
    Endpoint phụ để xem JSON ComposeDocResponse trả về từ Service A.
    Không dùng cho iframe, chỉ để debug / tích hợp khác nếu cần.
    """
    access_token = get_access_token(request)
    if not access_token:
        return JSONResponse({"detail": "unauthenticated"}, status_code=401)

    try:
        upstream = await _call_service_a_for_registration(
            access_token,
            project_code=project_code,
            cccd=cccd,
        )
    except httpx.RequestError as e:
        return JSONResponse(
            {"detail": f"Upstream Service A error: {e}"},
            status_code=502,
        )
    except Exception:
        return JSONResponse(
            {"detail": "Internal proxy error"},
            status_code=500,
        )

    return JSONResponse(upstream.get("data"), status_code=upstream.get("code", 200))
