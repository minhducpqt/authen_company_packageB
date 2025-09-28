# routers/customers.py
from __future__ import annotations
import os, httpx
from typing import Optional, List, Tuple
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from utils.templates import templates
from utils.auth import get_access_token

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter()

async def _api_get(client: httpx.AsyncClient, path: str, token: str, params: List[Tuple[str, str|int]]):
    r = await client.get(f"{API_BASE_URL}{path}",
                         headers={"Authorization": f"Bearer {token}"},
                         params=params, timeout=20.0)
    return r

@router.get("/customers", response_class=HTMLResponse)
async def customers_page(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=200),  # mặc định 50 cho mượt
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url=f"/login?next=%2Fcustomers", status_code=303)
    # Trang HTML chỉ render “khung”, dữ liệu do JS gọi JSON endpoint bên dưới
    return templates.TemplateResponse("customers/interactive.html", {
        "request": request,
        "title": "Khách hàng",
        "init_q": q or "",
        "init_page": page,
        "init_size": size,
    })

@router.get("/customers/data", response_class=JSONResponse)
async def customers_data(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=10, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str|int]] = [("page", page), ("size", size)]
    if q: params.append(("q", q))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/customers", token, params)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=200)
