# routers/auction_session_start_prices_display.py
"""Hall screen for one round's starting prices. Does not change the result display."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from utils.auth import get_access_token
from utils.templates import templates

router = APIRouter(tags=["auction_sessions:start-prices-display"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


@router.get("/auction/sessions/api/start-prices-board/sessions/{session_id}")
async def proxy_start_prices_board(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: Optional[int] = Query(None, ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    params: Dict[str, Any] = {}
    if round_no:
        params["round_no"] = round_no
    url = (
        f"{SERVICE_A_BASE_URL}/api/v1/auction-sessions/sessions/"
        f"{int(session_id)}/start-prices-board"
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)
    try:
        body = upstream.json()
    except Exception:
        body = {"detail": (upstream.text or "")[:300]}
    return JSONResponse(body, status_code=upstream.status_code)


@router.get("/auction/sessions/{session_id}/start-prices-display", response_class=HTMLResponse)
async def start_prices_display_page(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: Optional[int] = Query(None, ge=1),
):
    return templates.TemplateResponse(
        "auction_session/start_prices_display.html",
        {
            "request": request,
            "title": f"Trình chiếu giá khởi điểm — Phiên #{session_id}",
            "session_id": session_id,
            "round_no": round_no,
        },
    )
