from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.responses import StreamingResponse

from routers.mobile.service_a_client import (
    require_bearer,
    request_json_with_status,
    request_raw,
)

router = APIRouter(tags=["mobile-v1-mirror"])


def _upstream_path(full_path: str) -> str:
    """
    full_path is the path AFTER the mounted prefix.

    We mount this router under:
      /apis/mobile/v1

    Mobile calls:
      {B_BASE}/apis/mobile/v1/{A_ENDPOINT}

    Therefore upstream path MUST be exactly:
      /{A_ENDPOINT}
    Example:
      full_path="api/v1/projects" -> upstream="/api/v1/projects"
      full_path="public/deposit/..." -> upstream="/public/deposit/..."
    """
    p = "/" + (full_path or "").lstrip("/")
    return p if p != "/" else "/"


@router.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def mirror_all(
    request: Request,
    full_path: str,
    authorization: Optional[str] = Header(None),
):
    bearer = require_bearer(authorization)

    # Query params passthrough
    params: List[Tuple[str, Any]] = list(request.query_params.multi_items())

    upstream = _upstream_path(full_path)

    # Read body once for both json + raw fallback
    raw_body: bytes = b""
    try:
        raw_body = await request.body()
    except Exception:
        raw_body = b""

    # Parse JSON body if content-type is JSON
    json_body: Optional[Dict[str, Any]] = None
    if request.method in {"POST", "PUT", "PATCH"}:
        ct = (request.headers.get("content-type") or "").lower()
        if "application/json" in ct:
            try:
                json_body = await request.json()
            except Exception:
                json_body = None

    # 1) JSON-first (wrap)
    try:
        status_code, data = await request_json_with_status(
            request.method,
            upstream,
            headers={"Authorization": bearer},
            params=params,
            json=json_body,
        )
        return {
            "code": status_code,
            "message": "Success" if 200 <= status_code < 300 else "Error",
            "data": data,
        }

    except HTTPException as he:
        status = he.status_code
        detail = he.detail

        # 4xx: usually JSON error -> wrap as consistent envelope
        if 400 <= status < 500:
            raise HTTPException(
                status_code=status,
                detail={
                    "code": status,
                    "message": "Error",
                    "data": detail,
                },
            )

        # 5xx / content-type mismatch / file endpoints -> raw streaming fallback
        raw = await request_raw(
            request.method,
            upstream,
            headers={"Authorization": bearer},
            params=params,
            content=raw_body if raw_body else None,
            content_type=request.headers.get("content-type"),
        )

        # Forward headers (drop hop-by-hop)
        headers = {}
        for k, v in raw.headers.items():
            lk = k.lower()
            if lk in {"content-length", "transfer-encoding", "connection"}:
                continue
            headers[k] = v

        return StreamingResponse(
            raw.iter_bytes(),
            status_code=raw.status_code,
            headers=headers,
        )
