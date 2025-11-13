# routers/auction_docs.py
from __future__ import annotations

import os
from typing import Dict, Any

import httpx
from fastapi import APIRouter, Request, HTTPException, Query

from utils.auth import get_access_token, fetch_me  # dùng giống các router khác của B

# Đảm bảo biến này trùng convention bạn đang dùng:
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


@router.get("/auction/registration")
async def get_auction_registration_doc_proxy(
    request: Request,
    project_code: str = Query(..., description="Mã dự án"),
    cccd: str = Query(..., description="CCCD/CMND khách"),
):
    """
    Proxy từ WebAdmin (Service B) sang Service A để lấy
    'Đơn đăng ký tham gia đấu giá' của 1 khách.

    URL B (WebAdmin):
      GET /documents/auction/registration?project_code=...&cccd=...

    B sẽ gọi A:
      GET {SERVICE_A_BASE_URL}/api/v1/business/documents/auction/registration
          ?project_code=...&cccd=...
    """
    # Lấy access_token từ cookie / header giống các router khác
    access_token = get_access_token(request)
    if not access_token:
        raise HTTPException(status_code=401, detail="Unauthenticated")

    # Nếu cần info user (và company_scope) bên B, có thể gọi fetch_me(request)
    # nhưng ở đây A tự xác định company_scope từ token, nên không cần gửi company_code lên.
    params = {
        "project_code": project_code,
        "cccd": cccd,
    }

    headers = {
        # Pass token sang Service A theo kiểu Bearer (tuỳ fastapi-authen bạn config)
        "Authorization": f"Bearer {access_token}",
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            resp = await client.get(
                "/api/v1/business/documents/auction/registration",
                params=params,
                headers=headers,
            )

        # Nếu A trả về 404 hay 400 → forward thẳng cho FE
        if resp.status_code >= 400:
            try:
                data = resp.json()
            except Exception:
                data = {"detail": resp.text or "Upstream error"}
            raise HTTPException(status_code=resp.status_code, detail=data.get("detail", data))

        # 200 OK → dữ liệu ComposeDocResponse (JSON)
        return resp.json()

    except HTTPException:
        # đã xử lý ở trên, re-raise
        raise
    except httpx.RequestError as e:
        # Lỗi kết nối tới A → 502
        raise HTTPException(status_code=502, detail=f"Upstream Service A error: {e}")
    except Exception as e:
        # Lỗi khác trong proxy → 500
        raise HTTPException(status_code=500, detail="Internal proxy error")
