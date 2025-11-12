from __future__ import annotations
import os
from typing import Dict, Any, Optional

import httpx
from fastapi import Request

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


def _auth_headers(access: Optional[str]) -> dict:
    return {"Authorization": f"Bearer {access}"} if access else {}


class AuctionDocsClient:
    """
    Client gọi Service A để lấy payload dựng 'Đơn đăng ký tham gia đấu giá'.
    """
    def __init__(self, base_url: str = SERVICE_A_BASE_URL):
        self.base_url = base_url

    def get_registration_doc_payload(
        self,
        access: Optional[str],
        *,
        project_code: str,
        cccd: str,
    ) -> Dict[str, Any]:
        """
        Gọi A: /api/v1/business/documents/auction/registration
        Query: project_code, cccd
        """
        params = {
            "project_code": project_code,
            "cccd": cccd,
        }
        with httpx.Client(base_url=self.base_url, timeout=20.0) as c:
            r = c.get(
                "/api/v1/business/documents/auction/registration",
                headers=_auth_headers(access),
                params=params,
            )
        try:
            j = r.json()
        except Exception:
            j = None
        return {"code": r.status_code, "data": j}


auction_docs_client = AuctionDocsClient()


def fetch_registration_doc_payload(
    request: Request,
    project_code: str,
    cccd: str,
) -> Dict[str, Any]:
    """
    Lấy access token từ request (nếu có) rồi gọi A.
    Trả về dict: {"code": http_status, "data": json|None}
    """
    access: Optional[str] = None

    try:
        from services.admin_client import get_access_token as _get_access_token  # type: ignore
        access = _get_access_token(request)
    except Exception:
        access = (
            request.cookies.get("ACCESS_COOKIE")
            or request.cookies.get("ACCESS_COOKIE_NAME")
            or None
        )

    return auction_docs_client.get_registration_doc_payload(
        access,
        project_code=project_code,
        cccd=cccd,
    )
