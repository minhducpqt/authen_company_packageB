# routers/api_proxy.py
from __future__ import annotations
import os
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/api", tags=["api-proxy"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


async def _get_json(client: httpx.AsyncClient, url: str, headers: dict, params: Dict[str, Any] | None = None):
    r = await client.get(url, headers=headers, params=params or {}, timeout=20.0)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"detail": r.text[:500]}


def _unauth():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


# ========= A) PROJECT OPTIONS (đổ dropdown) =========
# Service A: GET /api/v1/projects/public?company_code=...&status=ACTIVE
@router.get("/projects/options", response_class=JSONResponse)
async def project_options(request: Request, q: Optional[str] = Query(None)):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return _unauth()

    company_code = (me or {}).get("company_code")
    if not company_code:
        return JSONResponse({"error": "no_company_scope"}, status_code=400)

    params: Dict[str, Any] = {
        "company_code": company_code,
        "status": "ACTIVE",
        "page": 1,
        "size": 1000,
    }
    if q:
        params["q"] = q

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL) as client:
        st, data = await _get_json(client, "/api/v1/projects/public", {"Authorization": f"Bearer {token}"}, params)

    if st != 200 or not isinstance(data, dict):
        return JSONResponse({"error": "service_a_failed", "status": st, "body": data}, status_code=502)

    opts = []
    for p in data.get("data", []):
        opts.append({
            "id": p.get("id"),
            "project_code": p.get("project_code") or p.get("code"),
            "name": p.get("name") or p.get("project_name") or "",
        })
    return JSONResponse({"options": opts}, status_code=200)


# ========= B) TRANSACTIONS OVERVIEW (proxy ổn định) =========
# Service A: /api/v1/overview/applications|deposits|summary

async def _overview_proxy(
    request: Request,
    endpoint: str,
    project_code: Optional[str],
    q: Optional[str],
    page: int,
    size: int,
):
    token = get_access_token(request)
    if not token:
        return _unauth()

    params: Dict[str, Any] = {"page": page, "size": size}
    if project_code:
        params["project_code"] = project_code
    if q:
        params["q"] = q

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL) as client:
        st, data = await _get_json(client, endpoint, {"Authorization": f"Bearer {token}"}, params)

    if st == 401:
        return _unauth()
    if st != 200:
        return JSONResponse({"error": "service_a_failed", "status": st, "body": data}, status_code=502)
    return JSONResponse(data, status_code=200)


@router.get("/transactions/applications", response_class=JSONResponse)
async def transactions_applications_api(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    return await _overview_proxy(request, "/api/v1/overview/applications", project_code, q, page, size)


@router.get("/transactions/deposits", response_class=JSONResponse)
async def transactions_deposits_api(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    return await _overview_proxy(request, "/api/v1/overview/deposits", project_code, q, page, size)


@router.get("/transactions/summary", response_class=JSONResponse)
async def transactions_summary_api(
    request: Request,
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
):
    return await _overview_proxy(request, "/api/v1/overview/summary", project_code, q, page, size)
