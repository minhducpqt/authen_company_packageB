# routers/auction_session_winner_printing.py   (Service B - Admin Portal)
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Request, Path, Query, Body
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction_session_winner_printing"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824").rstrip("/")


# =========================================================
# Helpers
# =========================================================
def _log(msg: str):
    print(f"[AUCTION_WIN_PRINT_B] {msg}")


_SENSITIVE_KEYS = {
    "access_token",
    "authorization",
    "token",
    "phone",
    "cccd",
    "password",
    "secret",
}


def _mask_sensitive(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if lk in _SENSITIVE_KEYS:
                out[k] = "***"
            else:
                out[k] = _mask_sensitive(v)
        return out
    if isinstance(obj, list):
        return [_mask_sensitive(x) for x in obj]
    return obj


def _auth_headers(request: Request) -> Dict[str, str]:
    token = get_access_token(request)
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


async def _svc_get(request: Request, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = _auth_headers(request)
    _log(f"GET {url} params={_mask_sensitive(params or {})}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()


async def _svc_post(request: Request, path: str, json_body: Dict[str, Any]) -> Any:
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = _auth_headers(request)
    _log(f"POST {url} json={_mask_sensitive(json_body)}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=json_body)
        r.raise_for_status()
        return r.json()


def _as_int(v: Any, default: int = 0) -> int:
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


# =========================================================
# Payloads (selected)
# =========================================================
class SelectedWinnerItem(BaseModel):
    session_id: int = Field(..., ge=1)
    lot_id: int = Field(..., ge=1)


class SelectedWinnerPayload(BaseModel):
    items: List[SelectedWinnerItem] = Field(default_factory=list)


# =========================================================
# A) PROXY JSON APIs (để UI gọi)
#    Map 1-1 với Service A:
#      /api/v1/auction-sessions/print/...
# =========================================================
@router.get("/auction/sessions/api/print/sessions/{session_id}/winners")
async def api_get_session_winners_json(
    request: Request,
    session_id: int = Path(..., ge=1),
):
    data = await _svc_get(request, f"/api/v1/auction-sessions/print/sessions/{session_id}/winners")
    return JSONResponse(content=data)


@router.get("/auction/sessions/api/print/sessions/{session_id}/rounds/{round_no}/winners")
async def api_get_round_winners_json(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: int = Path(..., ge=1),
):
    data = await _svc_get(
        request,
        f"/api/v1/auction-sessions/print/sessions/{session_id}/rounds/{round_no}/winners",
    )
    return JSONResponse(content=data)


@router.get("/auction/sessions/api/print/sessions/{session_id}/rounds/{round_no}/lots/{lot_code}")
async def api_get_one_lot_winner_json(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: int = Path(..., ge=1),
    lot_code: str = Path(..., min_length=1),
):
    data = await _svc_get(
        request,
        f"/api/v1/auction-sessions/print/sessions/{session_id}/rounds/{round_no}/lots/{lot_code}",
    )
    return JSONResponse(content=data)


@router.get("/auction/sessions/api/print/sessions/{session_id}/customers/{customer_id}/winners")
async def api_get_customer_winners_json(
    request: Request,
    session_id: int = Path(..., ge=1),
    customer_id: int = Path(..., ge=1),
):
    data = await _svc_get(
        request,
        f"/api/v1/auction-sessions/print/sessions/{session_id}/customers/{customer_id}/winners",
    )
    return JSONResponse(content=data)


@router.get("/auction/sessions/api/print/round-lots/{round_lot_id}/winner")
async def api_get_round_lot_winner_json(
    request: Request,
    round_lot_id: int = Path(..., ge=1),
):
    data = await _svc_get(request, f"/api/v1/auction-sessions/print/round-lots/{round_lot_id}/winner")
    return JSONResponse(content=data)


@router.post("/auction/sessions/api/print/winners/selected")
async def api_get_selected_winners_json(
    request: Request,
    payload: SelectedWinnerPayload = Body(...),
):
    data = await _svc_post(
        request,
        "/api/v1/auction-sessions/print/winners/selected",
        json_body=payload.model_dump(),
    )
    return JSONResponse(content=data)


# =========================================================
# B) PRINT PAGES (SSR HTML) — gọi Service A, render template
# =========================================================
@router.get("/auction/sessions/{session_id}/winners/print", response_class=HTMLResponse)
async def page_print_session_winners(
    request: Request,
    session_id: int = Path(..., ge=1),
):
    data = await _svc_get(request, f"/api/v1/auction-sessions/print/sessions/{session_id}/winners")

    return templates.TemplateResponse(
        "pages/auction_session_documents/winner_print.html",
        {
            "request": request,
            "title": "In phiếu trúng đấu giá (toàn phiên)",
            "mode": "SESSION",
            "session": data.get("session") or {},
            "project": data.get("project") or {},
            "round": None,
            "customer": None,
            "items": data.get("items") or [],
            "total_items": _as_int(data.get("total_winners"), 0),
            "raw": data,
        },
    )


@router.get("/auction/sessions/{session_id}/rounds/{round_no}/winners/print", response_class=HTMLResponse)
async def page_print_round_winners(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: int = Path(..., ge=1),
):
    data = await _svc_get(
        request,
        f"/api/v1/auction-sessions/print/sessions/{session_id}/rounds/{round_no}/winners",
    )

    return templates.TemplateResponse(
        "pages/auction_session_documents/winner_print.html",
        {
            "request": request,
            "title": f"In phiếu trúng đấu giá (vòng {round_no})",
            "mode": "ROUND",
            "session": data.get("session") or {},
            "project": data.get("project") or {},
            "round": data.get("round") or {},
            "customer": None,
            "items": data.get("items") or [],
            "total_items": _as_int(data.get("total_winners"), 0),
            "raw": data,
        },
    )


@router.get(
    "/auction/sessions/{session_id}/customers/{customer_id}/winners/print",
    response_class=HTMLResponse,
)
async def page_print_customer_winners_in_session(
    request: Request,
    session_id: int = Path(..., ge=1),
    customer_id: int = Path(..., ge=1),
):
    data = await _svc_get(
        request,
        f"/api/v1/auction-sessions/print/sessions/{session_id}/customers/{customer_id}/winners",
    )

    return templates.TemplateResponse(
        "pages/auction_session_documents/winner_print.html",
        {
            "request": request,
            "title": "In phiếu trúng đấu giá (theo khách hàng)",
            "mode": "CUSTOMER",
            "session": data.get("session") or {},
            "project": data.get("project") or {},
            "round": None,
            "customer": data.get("customer") or {},
            "items": data.get("items") or [],
            "total_items": _as_int(data.get("total_winners"), 0),
            "raw": data,
        },
    )


@router.get("/auction/sessions/round-lots/{round_lot_id}/winner/print", response_class=HTMLResponse)
async def page_print_by_round_lot_id(
    request: Request,
    round_lot_id: int = Path(..., ge=1),
):
    data = await _svc_get(request, f"/api/v1/auction-sessions/print/round-lots/{round_lot_id}/winner")

    return templates.TemplateResponse(
        "pages/auction_session_documents/winner_print.html",
        {
            "request": request,
            "title": "In phiếu trúng đấu giá (lẻ theo lô-vòng)",
            "mode": "ROUND_LOT",
            "session": data.get("session") or {},
            "project": data.get("project") or {},
            "round": data.get("round") or {},
            "customer": (data.get("winner") or {}).get("customer") or {},
            "items": [data.get("winner")] if data.get("winner") else [],
            "winner": data.get("winner") or {},
            "total_items": 1 if data.get("winner") else 0,
            "raw": data,
        },
    )


# ---- selected: hỗ trợ 2 cách ----
# (1) POST HTML: UI submit form/json
# (2) GET HTML: nhận query items=SID:LOTID,SID:LOTID,...
@router.post("/auction/sessions/winners/selected/print", response_class=HTMLResponse)
async def page_print_selected_winners_post(
    request: Request,
    payload: SelectedWinnerPayload = Body(...),
):
    data = await _svc_post(
        request,
        "/api/v1/auction-sessions/print/winners/selected",
        json_body=payload.model_dump(),
    )

    groups = data.get("groups") or []
    total_items = _as_int(data.get("total_items"), 0)

    return templates.TemplateResponse(
        "pages/auction_session_documents/winner_print.html",
        {
            "request": request,
            "title": "In phiếu trúng đấu giá (chọn nhiều)",
            "mode": "SELECTED",
            "groups": groups,
            "total_groups": _as_int(data.get("total_groups"), 0),
            "total_items": total_items,
            "raw": data,
        },
    )


@router.get("/auction/sessions/winners/selected/print", response_class=HTMLResponse)
async def page_print_selected_winners_get(
    request: Request,
    items: str = Query("", description="Format: SID:LOTID,SID:LOTID,..."),
):
    parsed: List[Dict[str, int]] = []
    raw = (items or "").strip()
    if raw:
        for part in raw.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            sid_s, lot_s = part.split(":", 1)
            sid = _as_int(sid_s, 0)
            lot = _as_int(lot_s, 0)
            if sid > 0 and lot > 0:
                parsed.append({"session_id": sid, "lot_id": lot})

    data = await _svc_post(
        request,
        "/api/v1/auction-sessions/print/winners/selected",
        json_body={"items": parsed},
    )

    groups = data.get("groups") or []
    total_items = _as_int(data.get("total_items"), 0)

    return templates.TemplateResponse(
        "pages/auction_session_documents/winner_print.html",
        {
            "request": request,
            "title": "In phiếu trúng đấu giá (chọn nhiều)",
            "mode": "SELECTED",
            "groups": groups,
            "total_groups": _as_int(data.get("total_groups"), 0),
            "total_items": total_items,
            "raw": data,
        },
    )
