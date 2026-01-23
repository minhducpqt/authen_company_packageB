# routers/auction_session_display.py  (Service B - Admin Portal)
from __future__ import annotations

import os
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, Request, Path, Query
from fastapi.responses import HTMLResponse, JSONResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction_sessions:display"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# =========================================================
# Helpers
# =========================================================
def _log(msg: str):
    print(f"[AUCTION_SESS_DISPLAY_B] {msg}")


_SENSITIVE_KEYS = {"phone", "cccd", "token", "access_token", "authorization"}


def _mask(obj: Any) -> Any:
    """Mask log payload to avoid leaking sensitive fields."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k and str(k).lower() in _SENSITIVE_KEYS:
                out[k] = "***"
            else:
                out[k] = _mask(v)
        return out
    if isinstance(obj, list):
        return [_mask(x) for x in obj]
    return obj


def _auth_headers(request: Request) -> Dict[str, str]:
    token = get_access_token(request)
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


async def _get_json_or_text(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"detail": resp.text}


async def _a_get(
    client: httpx.AsyncClient,
    request: Request,
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> tuple[int, Any]:
    """
    Call Service A GET, return (status_code, json_or_text)
    """
    base = SERVICE_A_BASE_URL.rstrip("/")
    url = f"{base}{path}"
    headers = _auth_headers(request)

    _log(f"GET {url} params={_mask(params)} body=None")
    r = await client.get(url, params=params, headers=headers)
    js = await _get_json_or_text(r)
    _log(f"-> {r.status_code} GET {r.request.url}")
    return r.status_code, js


# =========================================================
# Proxy: GET display payload (call Service A display API directly)
#   B: /auction/sessions/api/display/sessions/{session_id}?round_no=...
#   A: /api/v1/auction-sessions/display/sessions/{session_id}?round_no=...
# =========================================================
@router.get("/auction/sessions/api/display/sessions/{session_id}")
async def proxy_display_payload(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: Optional[int] = Query(None, ge=1),
):
    """
    Proxy thẳng sang Service A display payload.
    Trả nguyên status_code + body từ A để UI tự xử lý.
    """
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            params: Dict[str, Any] = {}
            if round_no:
                params["round_no"] = round_no

            st, js = await _a_get(
                client,
                request,
                f"/api/v1/auction-sessions/display/sessions/{session_id}",
                params=params,
            )
            return JSONResponse(status_code=st, content=js)

    except httpx.RequestError as e:
        _log(f"ERROR proxy_display_payload request_error: {e}")
        return JSONResponse(
            status_code=502,
            content={"detail": "Service A unavailable", "error": str(e)},
        )
    except Exception as e:
        _log(f"ERROR proxy_display_payload unexpected: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error", "error": str(e)},
        )


# =========================================================
# SSR page: trình chiếu
#   /auction/sessions/{session_id}/display?round_no=...
# =========================================================
@router.get("/auction/sessions/{session_id}/display", response_class=HTMLResponse)
async def display_page(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: Optional[int] = Query(None, ge=1),
):
    # Trang chỉ render khung; data fetch qua proxy JSON ở trên để tự refresh.
    return templates.TemplateResponse(
        "auction_session/display.html",
        {
            "request": request,
            "title": f"Trình chiếu kết quả — Phiên #{session_id}",
            "session_id": session_id,
            "round_no": round_no,
        },
    )
