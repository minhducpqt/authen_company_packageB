# routers/registration_form_collections.py
from __future__ import annotations

import os
from typing import List, Optional, Tuple

import httpx
from fastapi import APIRouter, Request, Query, Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.auth import get_access_token, fetch_me
from utils.templates import templates

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter()


async def _api_get(
    client: httpx.AsyncClient,
    path: str,
    token: str,
    params: List[Tuple[str, str | int]] | None = None,
):
    return await client.get(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        timeout=25.0,
    )


@router.get("/registration-forms/collections", response_class=HTMLResponse)
async def collections_page(
    request: Request,
    project_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    collection_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url="/login?next=%2Fregistration-forms%2Fcollections",
            status_code=303,
        )

    me = await fetch_me(token)
    company_code = (me or {}).get("company_code") or ""

    return templates.TemplateResponse(
        "pages/registration_forms/collections.html",
        {
            "request": request,
            "title": "Quản lý đơn thu",
            "company_code": company_code,
            "init_q": q or "",
            "init_page": page,
            "init_size": size,
            "init_project_id": project_id or "",
            "init_collection_status": collection_status or "",
        },
    )


@router.get("/registration-forms/collections/revision", response_class=JSONResponse)
async def collections_revision(
    request: Request,
    project_id: int = Query(..., ge=1),
    since: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("project_id", project_id)]
    if since:
        params.append(("since", since))

    async with httpx.AsyncClient() as client:
        r = await _api_get(
            client,
            "/api/v1/registration-forms/collections/revision",
            token,
            params,
        )

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=r.status_code)


@router.get("/registration-forms/collections/data", response_class=JSONResponse)
async def collections_data(
    request: Request,
    project_id: int = Query(..., ge=1),
    q: Optional[str] = Query(None),
    collection_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [
        ("project_id", project_id),
        ("page", page),
        ("size", size),
    ]
    if q:
        params.append(("q", q))
    if collection_status:
        params.append(("collection_status", collection_status))

    async with httpx.AsyncClient() as client:
        r = await _api_get(
            client,
            "/api/v1/registration-forms/collections/summary",
            token,
            params,
        )

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=r.status_code)


@router.get(
    "/registration-forms/collections/customers/{customer_id}/submissions",
    response_class=JSONResponse,
)
async def customer_submissions_data(
    request: Request,
    customer_id: int = Path(..., ge=1),
    project_id: int = Query(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("project_id", project_id)]

    async with httpx.AsyncClient() as client:
        r = await _api_get(
            client,
            f"/api/v1/registration-forms/collections/customers/{customer_id}/submissions",
            token,
            params,
        )

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    return JSONResponse(r.json(), status_code=r.status_code)
