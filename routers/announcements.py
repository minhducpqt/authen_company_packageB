# routers/announcements.py
from __future__ import annotations

import os
from typing import Optional, List, Tuple, Dict, Any

import httpx
from fastapi import APIRouter, Request, Query, Path
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
    params: List[Tuple[str, str | int]] | None = None,
):
    return await client.get(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        timeout=20.0,
    )


async def _api_post_json(
    client: httpx.AsyncClient, path: str, token: str, payload: Dict[str, Any]
):
    return await client.post(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=20.0,
    )


async def _api_put_json(
    client: httpx.AsyncClient, path: str, token: str, payload: Dict[str, Any]
):
    return await client.put(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=20.0,
    )


async def _api_delete(
    client: httpx.AsyncClient, path: str, token: str
):
    return await client.delete(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    )


# -----------------------
# Common helpers
# -----------------------
def _redirect_login(next_path: str) -> RedirectResponse:
    # next= urlencoded đơn giản (đủ dùng)
    # nếu bạn có helper encode riêng thì thay sau
    return RedirectResponse(url=f"/login?next={next_path}", status_code=303)


def _clamp_size(size: int) -> int:
    # theo yêu cầu: size mặc định 20, max 20
    if size <= 0:
        return 20
    return min(size, 20)


# ======================================
# LIST PAGE (HTML) + DATA (JSON)
# ======================================
@router.get("/announcements", response_class=HTMLResponse)
async def announcements_page(
    request: Request,
    q: Optional[str] = Query(None),
    status: str = Query("ALL"),          # ALL|DRAFT|PUBLISHED|ARCHIVED (phụ thuộc Service A)
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=20),
):
    token = get_access_token(request)
    if not token:
        return _redirect_login("%2Fannouncements")

    # SSR shell: FE sẽ gọi /announcements/data để load
    return templates.TemplateResponse(
        "announcements/index.html",
        {
            "request": request,
            "title": "Quản lý thông báo",
            "init_q": q or "",
            "init_status": status or "ALL",
            "init_page": page,
            "init_size": _clamp_size(size),
        },
    )


@router.get("/announcements/data", response_class=JSONResponse)
async def announcements_data(
    request: Request,
    q: Optional[str] = Query(None),
    status: str = Query("ALL"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=20),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    size = _clamp_size(size)
    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if q:
        params.append(("q", q.strip()))
    if status:
        params.append(("status", status.strip().upper()))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/announcements", token, params)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    # Service A trả {data,page,size,total}
    return JSONResponse(r.json(), status_code=r.status_code)


# ======================================
# CREATE / UPDATE / DELETE proxies
# (dùng POST để dễ submit form)
# ======================================
@router.post("/announcements/create", response_class=JSONResponse)
async def announcements_create(
    request: Request,
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    payload: Dict[str, Any] = {}
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        form = await request.form()
        payload = {
            "title": (form.get("title") or "").strip() or None,
            "summary": (form.get("summary") or "").strip() or None,
            "category": (form.get("category") or "").strip() or None,
            "publish_date": (form.get("publish_date") or "").strip() or None,  # YYYY-MM-DD
            "link_url": (form.get("link_url") or "").strip() or None,
            "status": (form.get("status") or "PUBLISHED").strip().upper(),
            "pinned": str(form.get("pinned") or "").lower() in ("1", "true", "yes", "on"),
            "sort_order": int(form.get("sort_order") or 0),
        }

    async with httpx.AsyncClient() as client:
        r = await _api_post_json(client, "/api/v1/announcements", token, payload)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if r.status_code >= 400:
        try:
            body = r.json()
        except Exception:
            body = {"detail": r.text[:400]}
        return JSONResponse(body, status_code=r.status_code)

    return JSONResponse(r.json(), status_code=200)


@router.post("/announcements/{announcement_id}/update", response_class=JSONResponse)
async def announcements_update(
    request: Request,
    announcement_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    payload: Dict[str, Any] = {}
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        form = await request.form()
        payload = {
            "title": (form.get("title") or "").strip() or None,
            "summary": (form.get("summary") or "").strip() or None,
            "category": (form.get("category") or "").strip() or None,
            "publish_date": (form.get("publish_date") or "").strip() or None,
            "link_url": (form.get("link_url") or "").strip() or None,
            "status": (form.get("status") or "").strip().upper() or None,
            "pinned": str(form.get("pinned") or "").lower() in ("1", "true", "yes", "on"),
            "sort_order": int(form.get("sort_order") or 0),
        }

    async with httpx.AsyncClient() as client:
        r = await _api_put_json(
            client, f"/api/v1/announcements/{announcement_id}", token, payload
        )

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if r.status_code >= 400:
        try:
            body = r.json()
        except Exception:
            body = {"detail": r.text[:400]}
        return JSONResponse(body, status_code=r.status_code)

    return JSONResponse(r.json(), status_code=200)


@router.post("/announcements/{announcement_id}/delete", response_class=JSONResponse)
async def announcements_delete(
    request: Request,
    announcement_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # Service A: DELETE /api/v1/announcements/{id} (soft delete -> ARCHIVED)
    async with httpx.AsyncClient() as client:
        r = await _api_delete(client, f"/api/v1/announcements/{announcement_id}", token)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if r.status_code >= 400:
        try:
            body = r.json()
        except Exception:
            body = {"detail": r.text[:400]}
        return JSONResponse(body, status_code=r.status_code)

    # Thường Service A trả {"ok": True} hoặc {"ok":True,"data":...}
    try:
        body = r.json()
    except Exception:
        body = {"ok": True}

    return JSONResponse(body, status_code=200)
