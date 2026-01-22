# routers/auction_session_bid_sheets.py  (Service B - Admin Portal)
from __future__ import annotations

import os
from typing import Optional, Dict, Any, List
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request, Query, Path, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/auction-sessions/bid-sheets", tags=["auction_session_bid_sheets"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# =========================================================
# Helpers
# =========================================================
def _log(msg: str):
    print(f"[AUCTION_BID_SHEETS_B] {msg}")


async def _get_json(client: httpx.AsyncClient, url: str, headers: dict, params: dict | None = None):
    r = await client.get(url, headers=headers, params=params)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


async def _post_json(client: httpx.AsyncClient, url: str, headers: dict, payload: dict):
    r = await client.post(url, headers=headers, json=payload)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


# =========================================================
# PAGE: ENTRY (redirect to session page usually)
# =========================================================
@router.get("", response_class=HTMLResponse)
async def bid_sheets_home(request: Request):
    """
    Trang entry đơn giản (có thể redirect về /auction/sessions).
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote('/auction-sessions/bid-sheets')}", status_code=303)

    return templates.TemplateResponse(
        "auction_session_bid_sheets/index.html",
        {
            "request": request,
            "title": "In phiếu trả giá (Phiên đấu giá)",
            "me": me,
        },
    )


# =========================================================
# PRINT: theo 1 ROUND_LOT (1 lô trong 1 vòng)
# =========================================================
@router.get("/print/round-lots/{round_lot_id}", response_class=HTMLResponse)
async def print_bid_sheets_for_round_lot(
    request: Request,
    round_lot_id: int = Path(..., ge=1),
    sort_mode: str = Query("STT_LOT", description="STT_LOT (default) | LOT_STT"),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote(f'/auction-sessions/bid-sheets/print/round-lots/{round_lot_id}')}",
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
            st, js = await _get_json(
                client,
                f"/api/v1/report/auction-sessions/round-lots/{int(round_lot_id)}/bid-sheets",
                headers,
                params={"sort_mode": sort_mode},
            )
        if st != 200 or not isinstance(js, dict):
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu (HTTP {st}).</p>",
                status_code=500,
            )
        tickets = js.get("data") or []
        meta = js.get("meta") or {}
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not tickets:
        return HTMLResponse("<h1>Không có phiếu nào để in.</h1>", status_code=404)

    # Render lại template print cũ (tái sử dụng)
    return templates.TemplateResponse(
        "pages/bid_tickets/print.html",
        {
            "request": request,
            "me": me,
            "tickets": tickets,
            "print_ctx": {
                "mode": "AUCTION_SESSION_ROUND_LOT",
                "round_lot_id": int(round_lot_id),
                "sort_mode": (sort_mode or "").upper(),
                **(meta or {}),
            },
        },
    )


# =========================================================
# PRINT: theo ROUND (tất cả lô của 1 vòng)
# =========================================================
@router.get("/print/rounds/{round_id}", response_class=HTMLResponse)
async def print_bid_sheets_for_round(
    request: Request,
    round_id: int = Path(..., ge=1),
    sort_mode: str = Query("STT_LOT", description="STT_LOT (default) | LOT_STT"),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote(f'/auction-sessions/bid-sheets/print/rounds/{round_id}')}",
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=60.0) as client:
            st, js = await _get_json(
                client,
                f"/api/v1/report/auction-sessions/rounds/{int(round_id)}/bid-sheets",
                headers,
                params={"sort_mode": sort_mode},
            )
        if st != 200 or not isinstance(js, dict):
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu (HTTP {st}).</p>",
                status_code=500,
            )
        tickets = js.get("data") or []
        meta = js.get("meta") or {}
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not tickets:
        return HTMLResponse("<h1>Không có phiếu nào để in.</h1>", status_code=404)

    return templates.TemplateResponse(
        "pages/bid_tickets/print.html",
        {
            "request": request,
            "me": me,
            "tickets": tickets,
            "print_ctx": {
                "mode": "AUCTION_SESSION_ROUND",
                "round_id": int(round_id),
                "sort_mode": (sort_mode or "").upper(),
                **(meta or {}),
            },
        },
    )


# =========================================================
# PRINT: theo SESSION (tất cả vòng/lô trong phiên)
# =========================================================
@router.get("/print/sessions/{session_id}", response_class=HTMLResponse)
async def print_bid_sheets_for_session(
    request: Request,
    session_id: int = Path(..., ge=1),
    sort_mode: str = Query("STT_LOT", description="STT_LOT (default) | LOT_STT"),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(
            url=f"/login?next={quote(f'/auction-sessions/bid-sheets/print/sessions/{session_id}')}",
            status_code=303,
        )

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=90.0) as client:
            st, js = await _get_json(
                client,
                f"/api/v1/report/auction-sessions/sessions/{int(session_id)}/bid-sheets",
                headers,
                params={"sort_mode": sort_mode},
            )
        if st != 200 or not isinstance(js, dict):
            return HTMLResponse(
                f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu (HTTP {st}).</p>",
                status_code=500,
            )
        tickets = js.get("data") or []
        meta = js.get("meta") or {}
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not tickets:
        return HTMLResponse("<h1>Không có phiếu nào để in.</h1>", status_code=404)

    return templates.TemplateResponse(
        "pages/bid_tickets/print.html",
        {
            "request": request,
            "me": me,
            "tickets": tickets,
            "print_ctx": {
                "mode": "AUCTION_SESSION_SESSION",
                "session_id": int(session_id),
                "sort_mode": (sort_mode or "").upper(),
                **(meta or {}),
            },
        },
    )


# =========================================================
# PRINT ONE: 1 khách + 1 round_lot (dùng selected bulk, không cần endpoint one)
# =========================================================
@router.get("/print/one", response_class=HTMLResponse)
async def print_one_bid_sheet(
    request: Request,
    round_lot_id: int = Query(..., ge=1),
    customer_id: int = Query(..., ge=1),
    sort_mode: str = Query("STT_LOT"),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote('/auction-sessions/bid-sheets/print/one')}", status_code=303)

    headers = {"Authorization": f"Bearer {token}"}
    payload = {"items": [{"round_lot_id": int(round_lot_id), "customer_id": int(customer_id)}], "sort_mode": sort_mode}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
            st, js = await _post_json(
                client,
                "/api/v1/report/auction-sessions/bid-sheets/selected",
                headers,
                payload,
            )
        if st != 200 or not isinstance(js, dict):
            return HTMLResponse(f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu (HTTP {st}).</p>", status_code=500)
        tickets = js.get("data") or []
        meta = js.get("meta") or {}
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not tickets:
        return HTMLResponse("<h1>Không tìm thấy phiếu để in.</h1>", status_code=404)

    return templates.TemplateResponse(
        "pages/bid_tickets/print.html",
        {
            "request": request,
            "me": me,
            "tickets": tickets,
            "print_ctx": {
                "mode": "AUCTION_SESSION_ONE",
                "round_lot_id": int(round_lot_id),
                "customer_id": int(customer_id),
                "sort_mode": (sort_mode or "").upper(),
                **(meta or {}),
            },
        },
    )


# =========================================================
# PRINT SELECTED: nhiều ticket theo tick chọn trên UI
# item = "<round_lot_id>|<customer_id>"
# =========================================================
def _parse_item(s: str) -> Optional[tuple[int, int]]:
    try:
        parts = (s or "").split("|")
        if len(parts) != 2:
            return None
        rlid = int(parts[0])
        cid = int(parts[1])
        if rlid <= 0 or cid <= 0:
            return None
        return rlid, cid
    except Exception:
        return None


@router.get("/print/selected", response_class=HTMLResponse)
async def print_selected_bid_sheets(
    request: Request,
    item: List[str] = Query(..., description="Repeated: <round_lot_id>|<customer_id>"),
    sort_mode: str = Query("STT_LOT"),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote('/auction-sessions/bid-sheets/print/selected')}", status_code=303)

    parsed: List[Dict[str, int]] = []
    seen = set()
    for s in item or []:
        t = _parse_item(s)
        if not t:
            continue
        if t in seen:
            continue
        seen.add(t)
        parsed.append({"round_lot_id": int(t[0]), "customer_id": int(t[1])})

    if not parsed:
        return HTMLResponse("<h1>Không có phiếu hợp lệ để in.</h1>", status_code=400)

    payload = {"items": parsed, "sort_mode": sort_mode}
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=60.0) as client:
            st, js = await _post_json(
                client,
                "/api/v1/report/auction-sessions/bid-sheets/selected",
                headers,
                payload,
            )
        if st != 200 or not isinstance(js, dict):
            return HTMLResponse(f"<h1>Lỗi</h1><p>Không lấy được dữ liệu phiếu (HTTP {st}).</p>", status_code=500)
        tickets = js.get("data") or []
        meta = js.get("meta") or {}
    except Exception as e:
        return HTMLResponse(f"<h1>Lỗi</h1><p>{e}</p>", status_code=500)

    if not tickets:
        return HTMLResponse("<h1>Không có phiếu nào để in.</h1>", status_code=404)

    return templates.TemplateResponse(
        "pages/bid_tickets/print.html",
        {
            "request": request,
            "me": me,
            "tickets": tickets,
            "print_ctx": {
                "mode": "AUCTION_SESSION_SELECTED",
                "sort_mode": (sort_mode or "").upper(),
                **(meta or {}),
            },
        },
    )
