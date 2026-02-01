# routers/mobile/service_a_client.py
from __future__ import annotations

import os
from typing import Optional, Any, Dict, List, Tuple

import httpx
from fastapi import HTTPException


SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

# Mobile APIs đa phần là JSON, dùng chung timeout.
# Bạn có thể chỉnh env API_HTTP_TIMEOUT / AUTH_HTTP_TIMEOUT, mặc định 8s.
DEFAULT_TIMEOUT = float(os.getenv("API_HTTP_TIMEOUT", os.getenv("AUTH_HTTP_TIMEOUT", "8.0")))


def require_bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return authorization


async def request_json(
    method: str,
    path: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[List[Tuple[str, Any]]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """
    Proxy request to Service A, return JSON (preferred) or {"ok": True}.
    If upstream returns error, raise HTTPException with the upstream status + detail.
    """
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=timeout) as client:
            r = await client.request(
                method=method,
                url=path,
                headers=headers,
                params=params or [],
                json=json,
            )
    except httpx.RequestError as e:
        # network/dns/timeout/connect issues
        raise HTTPException(status_code=502, detail=f"Upstream Service A error: {str(e)}")

    # Upstream error passthrough
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise HTTPException(status_code=r.status_code, detail=detail)

    # Success: prefer JSON
    ctype = (r.headers.get("content-type") or "").lower()
    if ctype.startswith("application/json"):
        try:
            return r.json()
        except Exception:
            # rare: content-type json but body invalid
            return {"ok": True}

    # Success but non-JSON
    return {"ok": True}
