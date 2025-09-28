# routers/customers.py
from __future__ import annotations

import os
import httpx
from typing import Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter()

async def _fetch_json(client: httpx.AsyncClient, url: str, access: Optional[str]):
    headers = {}
    if access:
        headers["Authorization"] = f"Bearer {access}"
    r = await client.get(url, headers=headers, timeout=20.0)
    r.raise_for_status()
    return r.json()

@router.get("/customers", response_class=HTMLResponse)
async def page_customers(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(200, le=200),
):
    access = get_access_token(request)
    me = await fetch_me(request)

    params = [("page", page), ("size", size)]
    if q:
        params.append(("q", q))
    url = f"{API_BASE_URL}/api/v1/customers"
    async with httpx.AsyncClient() as client:
        resp = await _fetch_json(client, url, access)
    customers = resp.get("data", [])
    total = resp.get("total", 0)

    return templates.TemplateResponse(
        "customers/list.html",
        {
            "request": request,
            "me": me,
            "customers": customers,
            "q": q or "",
            "page": page,
            "size": size,
            "total": total,
            "title": "Khách hàng",
        },
    )
