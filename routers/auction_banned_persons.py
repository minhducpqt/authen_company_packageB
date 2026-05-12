# routers/auction_banned_persons.py
from __future__ import annotations

import os
from typing import Optional, List, Tuple

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter()


# -----------------------
# Internal HTTP helpers
# -----------------------
async def _api_get(
    client: httpx.AsyncClient,
    path: str,
    token: str,
    params: List[Tuple[str, str | int | bool]] | None = None,
):
    return await client.get(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        timeout=20.0,
    )


# ======================================
# LIST PAGE
# ======================================
@router.get("/auction-banned-persons", response_class=HTMLResponse)
async def auction_banned_persons_page(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    active_only: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=200),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Fauction-banned-persons",
            status_code=303,
        )

    return templates.TemplateResponse(
        "auction_banned_persons/interactive.html",
        {
            "request": request,
            "title": "Danh sách cấm đấu giá",
            "init_q": q or "",
            "init_status": status or "",
            "init_active_only": active_only,
            "init_page": page,
            "init_size": size,
        },
    )


# ======================================
# DATA JSON PROXY
# ======================================
@router.get("/auction-banned-persons/data", response_class=JSONResponse)
async def auction_banned_persons_data(
    request: Request,
    q: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    active_only: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int | bool]] = [
        ("page", page),
        ("size", size),
        ("active_only", active_only),
    ]

    if q:
        params.append(("q", q))

    if status:
        params.append(("status", status))

    async with httpx.AsyncClient() as client:
        r = await _api_get(
            client,
            "/api/v1/auction-banned-persons",
            token,
            params,
        )

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if r.status_code >= 500:
        return JSONResponse(
            {"error": "server", "msg": r.text[:500]},
            status_code=502,
        )

    if r.status_code >= 400:
        try:
            body = r.json()
        except Exception:
            body = {"detail": r.text[:500]}
        return JSONResponse(body, status_code=r.status_code)

    return JSONResponse(r.json(), status_code=200)


# ======================================
# CHECK CCCD JSON PROXY
# ======================================
@router.get("/auction-banned-persons/check", response_class=JSONResponse)
async def auction_banned_person_check(
    request: Request,
    cccd: str = Query(..., min_length=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async with httpx.AsyncClient() as client:
        r = await _api_get(
            client,
            "/api/v1/auction-banned-persons/check",
            token,
            [("cccd", cccd)],
        )

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if r.status_code >= 400:
        try:
            body = r.json()
        except Exception:
            body = {"detail": r.text[:500]}
        return JSONResponse(body, status_code=r.status_code)

    return JSONResponse(r.json(), status_code=200)