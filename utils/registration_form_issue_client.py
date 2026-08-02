# utils/registration_form_issue_client.py
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ISSUE_TIMEOUT = float(os.getenv("REGISTRATION_FORM_ISSUE_TIMEOUT", "15"))


async def issue_registration_form_qr(
    access_token: str,
    *,
    project_id: int,
    customer_id: int,
    source: str = "DEPOSITS_PAGE",
) -> Optional[str]:
    """
    Gọi Service A phát hành token QR (DKQ-...) cho đơn đăng ký.
    Trả về jti nếu thành công; None nếu lỗi (fail-safe cho in đơn).
    """
    if not access_token or not project_id or not customer_id:
        return None

    payload: Dict[str, Any] = {
        "project_id": int(project_id),
        "customer_id": int(customer_id),
        "source": (source or "DEPOSITS_PAGE").strip().upper(),
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=ISSUE_TIMEOUT) as client:
            resp = await client.post(
                "/api/v1/registration-forms/issues",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except Exception as exc:
        logger.warning("registration_form issue client error: %s", exc)
        return None

    if resp.status_code >= 400:
        logger.warning(
            "registration_form issue failed: HTTP %s body=%s",
            resp.status_code,
            resp.text[:300],
        )
        return None

    try:
        body = resp.json()
    except Exception:
        return None

    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        return None

    jti = (data.get("jti") or data.get("qr_token") or "").strip()
    return jti or None
