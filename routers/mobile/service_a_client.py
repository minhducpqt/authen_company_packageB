# routers/mobile/apis/service_a_client.py

from __future__ import annotations

import os
from typing import Optional, Any, Dict, List, Tuple

import httpx
from fastapi import HTTPException


SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

# Mobile APIs mostly JSON; shared timeout.
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
    Backward-compatible helper (used by older mobile routers).
    - On success: return JSON (preferred) or {"ok": True}
    - On upstream error: raise HTTPException(status_code, detail)
    """
    status_code, data = await request_json_with_status(
        method,
        path,
        headers=headers,
        params=params,
        json=json,
        timeout=timeout,
    )
    # Keep old behavior: ignore status_code
    return data


async def request_json_with_status(
    method: str,
    path: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[List[Tuple[str, Any]]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Tuple[int, Any]:
    """
    JSON helper WITH status code (used by mirror).
    - On success: returns (status_code, json_data or {"ok": True})
    - On upstream error: raises HTTPException(status_code, detail)
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
            return r.status_code, r.json()
        except Exception:
            # content-type says json but body is invalid
            return r.status_code, {"ok": True}

    # Success but non-JSON
    return r.status_code, {"ok": True}


async def request_raw(
    method: str,
    path: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[List[Tuple[str, Any]]] = None,
    content: Optional[bytes] = None,
    content_type: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.Response:
    """
    Raw proxy helper for file/binary endpoints (xlsx/pdf/...).

    Returns the upstream httpx.Response.
    Caller should stream bytes and forward headers as needed.

    On upstream error: raises HTTPException(status_code, detail).
    """
    h = dict(headers or {})

    # Forward content-type if provided
    if content_type and "content-type" not in {k.lower() for k in h.keys()}:
        h["Content-Type"] = content_type

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=timeout) as client:
            r = await client.request(
                method=method,
                url=path,
                headers=h,
                params=params or [],
                content=content,
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Upstream Service A error: {str(e)}")

    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise HTTPException(status_code=r.status_code, detail=detail)

    return r
