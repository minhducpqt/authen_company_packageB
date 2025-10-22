# ServiceB/routers/dossier_buyers.py
from __future__ import annotations
import os
import httpx
from typing import List, Tuple, Dict, Any, Optional

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter(tags=["send-info"])

# ---------- internal helpers ----------
async def _api_get(
    client: httpx.AsyncClient, path: str, token: str,
    params: List[Tuple[str, str | int]] | None = None
):
    return await client.get(
        f"{SERVICE_A_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        timeout=20.0,
    )

def _first_active_project_id(projects: list[dict]) -> Optional[int]:
    actives = [p for p in projects if str(p.get("status")).upper() == "ACTIVE"]
    if len(actives) == 1:
        return actives[0].get("id")
    return None

# ============== PAGE (SSR khung + preload projects & first page) ==============
@router.get("/thong-tin-khach-mua-ho-so", response_class=HTMLResponse)
async def dossier_buyers_page(
    request: Request,
    project_id: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=200),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fthong-tin-khach-mua-ho-so", status_code=303)

    # 1) Load projects (active)
    projects: list[dict] = []
    async with httpx.AsyncClient() as client:
        r_proj = await _api_get(client, "/api/v1/projects", token, [
            ("status", "ACTIVE"), ("page", 1), ("size", 1000)
        ])
    if r_proj.status_code == 200:
        try:
            projects = (r_proj.json() or {}).get("data", [])
        except Exception:
            projects = []

    # Nếu không chọn project_id và chỉ có đúng 1 active -> auto chọn
    if not project_id:
        auto = _first_active_project_id(projects)
        if auto:
            project_id = auto

    # 2) Preload trang 1 (nếu đã có project_id)
    page_data = {"page": page, "size": size, "total": 0, "data": []}
    if project_id:
        async with httpx.AsyncClient() as client:
            r = await _api_get(
                client,
                "/api/v1/dossier-orders/summary",
                token,
                [("project_id", project_id), ("page", page), ("size", size)],
            )
        if r.status_code == 200:
            try:
                page_data = r.json()
            except Exception:
                pass
        elif r.status_code == 401:
            return RedirectResponse(url="/login?next=%2Fthong-tin-khach-mua-ho-so", status_code=303)

    return templates.TemplateResponse(
        "send/dossier_buyers.html",
        {
            "request": request,
            "title": "4.1 Khách mua hồ sơ",
            "projects": projects,
            "selected_project_id": project_id or "",
            "page": page_data,
        },
    )

# ======================== DATA (AJAX fetch cho bảng) =========================
@router.get("/thong-tin-khach-mua-ho-so/data", response_class=JSONResponse)
async def dossier_buyers_data(
    request: Request,
    project_id: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=10, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async with httpx.AsyncClient() as client:
        r = await _api_get(
            client,
            "/api/v1/dossier-orders/summary",
            token,
            [("project_id", project_id), ("page", page), ("size", size)],
        )

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)

    try:
        return JSONResponse(r.json(), status_code=200)
    except Exception:
        return JSONResponse({"error": "bad_upstream"}, status_code=502)
