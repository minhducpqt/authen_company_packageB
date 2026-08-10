# routers/auction_group_session_v2.py — Service B
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Body, Path, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from utils.auth import get_access_token
from utils.templates import templates

router = APIRouter(tags=["auction_group_session_v2"])
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824").rstrip("/")


async def _a(
    method: str,
    path: str,
    token: str,
    *,
    json_body: Any = None,
    timeout: float = 60.0,
):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.request(method, url, headers=headers, json=json_body)
    try:
        js = r.json()
    except Exception:
        js = {"detail": (r.text or "")[:500]}
    return r.status_code, js if isinstance(js, dict) else {"data": js}


@router.get("/auction/sessions/{session_id}/group-v2", response_class=HTMLResponse)
async def group_v2_page(request: Request, session_id: int = Path(..., ge=1)):
    token = get_access_token(request)
    if not token:
        return templates.TemplateResponse(
            "pages/error.html",
            {"request": request, "title": "Chưa đăng nhập", "message": "Vui lòng đăng nhập lại."},
            status_code=401,
        )
    st, overview = await _a("GET", f"/api/v1/auction-sessions/group-v2/sessions/{session_id}/overview", token)
    # session meta
    st_s, sess = await _a("GET", f"/api/v1/auction-sessions/sessions/{session_id}", token)
    sess_data = (sess.get("data") or sess) if isinstance(sess, dict) else {}

    error = None
    if st != 200:
        error = {"status": st, "body": overview}

    return templates.TemplateResponse(
        "auction_session/group_v2.html",
        {
            "request": request,
            "title": f"Kết quả đấu nhóm v2 — phiên #{session_id}",
            "session_id": session_id,
            "session": sess_data if st_s == 200 else {},
            "overview": overview if st == 200 else {"groups": []},
            "error": error,
        },
    )


@router.get("/auction/sessions/api/group-v2/{session_id}/overview")
async def api_overview(request: Request, session_id: int = Path(..., ge=1)):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    st, js = await _a("GET", f"/api/v1/auction-sessions/group-v2/sessions/{session_id}/overview", token)
    return JSONResponse(js, status_code=st)


@router.get("/auction/sessions/api/group-v2/{session_id}/groups/{deposit_vnd}")
async def api_group_detail(
    request: Request,
    session_id: int = Path(..., ge=1),
    deposit_vnd: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    st, js = await _a(
        "GET",
        f"/api/v1/auction-sessions/group-v2/sessions/{session_id}/groups/{deposit_vnd}",
        token,
    )
    return JSONResponse(js, status_code=st)


@router.put("/auction/sessions/api/group-v2/{session_id}/groups/{deposit_vnd}/tickets")
async def api_replace_tickets(
    request: Request,
    session_id: int = Path(..., ge=1),
    deposit_vnd: int = Path(..., ge=1),
    body: Dict[str, Any] = Body(default={}),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    st, js = await _a(
        "PUT",
        f"/api/v1/auction-sessions/group-v2/sessions/{session_id}/groups/{deposit_vnd}/tickets",
        token,
        json_body=body,
    )
    return JSONResponse(js, status_code=st)


@router.post("/auction/sessions/api/group-v2/{session_id}/groups/{deposit_vnd}/confirm-winners")
async def api_confirm_winners(
    request: Request,
    session_id: int = Path(..., ge=1),
    deposit_vnd: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    st, js = await _a(
        "POST",
        f"/api/v1/auction-sessions/group-v2/sessions/{session_id}/groups/{deposit_vnd}/confirm-winners",
        token,
        json_body={},
    )
    return JSONResponse(js, status_code=st)


@router.post("/auction/sessions/api/group-v2/{session_id}/groups/{deposit_vnd}/assign-lot")
async def api_assign_lot(
    request: Request,
    session_id: int = Path(..., ge=1),
    deposit_vnd: int = Path(..., ge=1),
    body: Dict[str, Any] = Body(default={}),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    st, js = await _a(
        "POST",
        f"/api/v1/auction-sessions/group-v2/sessions/{session_id}/groups/{deposit_vnd}/assign-lot",
        token,
        json_body=body,
    )
    return JSONResponse(js, status_code=st)


@router.get("/auction/sessions/{session_id}/group-v2/print-r2/{deposit_vnd}", response_class=HTMLResponse)
async def print_round2(
    request: Request,
    session_id: int = Path(..., ge=1),
    deposit_vnd: int = Path(..., ge=1),
    round_no: Optional[int] = Query(None, ge=2, le=99),
):
    token = get_access_token(request)
    if not token:
        return templates.TemplateResponse(
            "pages/error.html",
            {"request": request, "title": "Chưa đăng nhập", "message": "Vui lòng đăng nhập."},
            status_code=401,
        )
    path = f"/api/v1/auction-sessions/group-v2/sessions/{session_id}/groups/{deposit_vnd}/round2-print"
    if round_no is not None:
        path = f"{path}?round_no={int(round_no)}"
    st, js = await _a("GET", path, token)
    return templates.TemplateResponse(
        "auction_session/group_v2_r2_print.html",
        {
            "request": request,
            "session_id": session_id,
            "deposit_vnd": deposit_vnd,
            "round_no": round_no,
            "data": js if st == 200 else {},
            "error": None if st == 200 else js,
        },
    )
