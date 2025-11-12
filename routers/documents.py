from __future__ import annotations
import datetime
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token
from services.auction_docs_client import fetch_registration_doc_payload

router = APIRouter()


@router.get("/documents/auction/registration", response_class=HTMLResponse)
async def view_auction_registration(
    request: Request,
    project_code: str = Query(..., description="Mã dự án"),
    cccd: str = Query(..., description="Số CCCD khách"),
    download: Optional[str] = Query(
        None, description="html -> tải file HTML; để trống -> hiển thị"
    ),
):
    """
    Hiển thị **Đơn đăng ký tham gia đấu giá** (HTML).
    - Nếu `download=html` thì trả về file đính kèm .html.
    - Mặc định trả về trang HTML để xem/Print to PDF từ trình duyệt.
    """
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Fdocuments%2Fauction%2Fregistration", status_code=303
        )

    # Gọi Service A lấy payload dựng đơn
    resp = fetch_registration_doc_payload(
        request, project_code=project_code, cccd=cccd
    )

    code = int(resp.get("code", 500))
    if code == 401:
        return RedirectResponse(url="/login", status_code=303)
    if code == 404:
        return HTMLResponse("<h3>Không tìm thấy dữ liệu.</h3>", status_code=404)
    if code >= 500:
        return HTMLResponse("<h3>Lỗi upstream (A).</h3>", status_code=502)

    data = resp.get("data") or {}

    today = datetime.date.today()
    html = templates.get_template("pages/documents/auction_registration.html").render(
        request=request,
        title="Đơn đăng ký tham gia đấu giá",
        data=data,
        today=today,
        year=today.year,
    )

    if download == "html":
        filename = f"{cccd}_{project_code}.html"
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return HTMLResponse(html)


@router.get("/documents/auction/registration/data", response_class=JSONResponse)
async def view_auction_registration_data(
    request: Request,
    project_code: str = Query(...),
    cccd: str = Query(...),
):
    """
    Endpoint JSON (nếu FE cần debug/test).
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    resp = fetch_registration_doc_payload(request, project_code=project_code, cccd=cccd)
    return JSONResponse(resp, status_code=resp.get("code", 200))
