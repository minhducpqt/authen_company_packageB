# routers/lots.py (Service B) - FINAL
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import APIRouter, Request, Query, Path, Body, HTTPException
from fastapi.responses import JSONResponse

from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/lots", tags=["lots"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

# ---- Service A endpoints (lots) ----
EP_LOTS_BASE = "/api/v1/lots"
EP_LOT_DETAIL = "/api/v1/lots/{lot_id}"
EP_LOT_LOCK = "/api/v1/lots/{lot_id}/lock"
EP_LOT_UNLOCK = "/api/v1/lots/{lot_id}/unlock"


# ==============================
# Shared helpers
# ==============================
def _merge_headers(
    *,
    token: Optional[str] = None,
    company_code: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Hợp nhất headers:
    - headers truyền vào là base
    - nếu chưa có Authorization và có token -> Bearer token
    - nếu có company_code -> set X-Company-Code (để import/apply dùng giống bản gốc)
    """
    h: Dict[str, str] = dict(headers or {})
    if token and not h.get("Authorization"):
        h["Authorization"] = f"Bearer {token}"
    if company_code:
        h["X-Company-Code"] = company_code
    return h


async def _safe_json(resp: httpx.Response) -> Optional[Dict[str, Any]]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"data": data}
    except Exception:
        return None


# =========================================================
# ✅ Helpers exported for reuse in projects.py
# =========================================================
async def sa_create_lot(
    client: httpx.AsyncClient,
    token: Optional[str] = None,
    lot_body: Optional[Dict[str, Any]] = None,
    company_code: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Helper tạo lot ở Service A.

    ✅ Tương thích 2 kiểu call:
      1) sa_create_lot(client, token, lot_body, company_code=...)
      2) sa_create_lot(client, headers=headers, lot_body=lot_body)

    Return: (status_code, json_or_none)
    """
    h = _merge_headers(token=token, company_code=company_code, headers=headers)
    body = lot_body or {}
    r = await client.post(EP_LOTS_BASE, json=body, headers=h)
    return r.status_code, await _safe_json(r)


async def sa_list_lots_by_project_code(
    client: httpx.AsyncClient,
    token: str,
    project_code: str,
    company_code: Optional[str] = None,
    size: int = 1000,
    page: int = 1,
    q: Optional[str] = None,
    status: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Helper list lots theo project_code từ Service A.
    Giữ đúng tinh thần bản gốc: gọi /api/v1/lots?project_code=...&size=1000 (+ page)
    """
    h = _merge_headers(token=token, company_code=company_code, headers=headers)

    params: Dict[str, Any] = {"project_code": project_code, "page": page, "size": size}
    if q:
        params["q"] = q
    if status:
        params["status"] = status

    r = await client.get(EP_LOTS_BASE, params=params, headers=h)
    return r.status_code, await _safe_json(r)


# =========================================================
# ✅ Router endpoints (Service B) - proxy to Service A
# (Additive, không phá logic endpoint cũ)
# =========================================================

@router.get("/api/list", response_class=JSONResponse)
async def api_list_lots(
    request: Request,
    project_code: str = Query(...),
    q: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(1000, ge=1, le=2000),
):
    """
    Proxy list lots: GET /lots/api/list?project_code=...
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    me = await fetch_me(token)
    company_code = (me or {}).get("company_code")

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=15.0) as client:
        st, data = await sa_list_lots_by_project_code(
            client,
            token=token,
            project_code=project_code,
            company_code=company_code,
            size=size,
            page=page,
            q=q,
            status=status,
        )

    return JSONResponse(data or {"error": "upstream_failed", "status": st}, status_code=st if st else 502)


@router.post("/api/create", response_class=JSONResponse)
async def api_create_lot(
    request: Request,
    payload: Dict[str, Any] = Body(...),
):
    """
    Proxy create lot: POST /lots/api/create
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    me = await fetch_me(token)
    company_code = (me or {}).get("company_code")

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
        st, data = await sa_create_lot(
            client,
            token=token,
            lot_body=payload,
            company_code=company_code or payload.get("company_code"),
        )
    return JSONResponse(data or {"error": "upstream_failed", "status": st}, status_code=st if st else 502)


@router.patch("/api/{lot_id}", response_class=JSONResponse)
async def api_update_lot(
    request: Request,
    lot_id: int = Path(...),
    payload: Dict[str, Any] = Body(...),
):
    """
    Proxy update lot: PATCH /lots/api/{lot_id}
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # Không ép company_code ở đây để giữ đúng behavior Service A (scope do token quyết định)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
        r = await client.patch(
            EP_LOT_DETAIL.format(lot_id=lot_id),
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        data = await _safe_json(r)
        return JSONResponse(data or {"error": "upstream_failed", "status": r.status_code}, status_code=r.status_code)


@router.post("/api/{lot_id}/lock", response_class=JSONResponse)
async def api_lock_lot(
    request: Request,
    lot_id: int = Path(...),
):
    """
    Proxy lock lot: POST /lots/api/{lot_id}/lock
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=15.0) as client:
        r = await client.post(
            EP_LOT_LOCK.format(lot_id=lot_id),
            headers={"Authorization": f"Bearer {token}"},
        )
        data = await _safe_json(r)
        return JSONResponse(data or {"error": "upstream_failed", "status": r.status_code}, status_code=r.status_code)


@router.post("/api/{lot_id}/unlock", response_class=JSONResponse)
async def api_unlock_lot(
    request: Request,
    lot_id: int = Path(...),
):
    """
    Proxy unlock lot: POST /lots/api/{lot_id}/unlock
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=15.0) as client:
        r = await client.post(
            EP_LOT_UNLOCK.format(lot_id=lot_id),
            headers={"Authorization": f"Bearer {token}"},
        )
        data = await _safe_json(r)
        return JSONResponse(data or {"error": "upstream_failed", "status": r.status_code}, status_code=r.status_code)
