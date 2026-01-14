# app/routers/auction_prints.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

import httpx
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import HTMLResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction:prints"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# ---------------- HTTP helpers ----------------
def _preview_body(data: Any, limit: int = 300) -> str:
    try:
        import json
        s = json.dumps(data, ensure_ascii=False)
    except Exception:
        s = str(data)
    if len(s) > limit:
        return s[:limit] + "...(truncated)"
    return s


async def _get_json(path: str, token: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = SERVICE_A_BASE_URL.rstrip("/") + path
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params=params or {})
        if r.status_code >= 400:
            try:
                body = r.json()
            except Exception:
                body = {"text": r.text}
            raise HTTPException(
                status_code=r.status_code,
                detail=f"Service A error {r.status_code} on GET {path}: {_preview_body(body)}",
            )
        return r.json()


# ---------------- A APIs (print-data) ----------------
async def fetch_project_print_data(project_id: int, token: str) -> Dict[str, Any]:
    return await _get_json(f"/api/v1/auction-results/print/projects/{project_id}", token)


async def fetch_lot_print_data(project_id: int, lot_code: str, token: str) -> Dict[str, Any]:
    return await _get_json(f"/api/v1/auction-results/print/projects/{project_id}/lots/{lot_code}", token)


# =========================================================
# 1) View/Print one winner slip
# =========================================================
@router.get(
    "/auction/prints/projects/{project_id}/lots/{lot_code}",
    response_class=HTMLResponse,
)
async def view_winner_slip(
    request: Request,
    project_id: int,
    lot_code: str,
):
    token = get_access_token(request)
    if not token:
        # tuỳ hệ auth của bạn: redirect login hoặc báo lỗi
        raise HTTPException(status_code=401, detail="Not logged in")

    data = await fetch_lot_print_data(project_id, lot_code, token)
    return templates.TemplateResponse(
        "auction/winner_slip.html",
        {
            "request": request,
            "data": data,
            "project": data.get("project") or {},
            "winner": data.get("winner") or {},
        },
    )


# =========================================================
# 2) View/Print all winner slips in a project
# =========================================================
@router.get(
    "/auction/prints/projects/{project_id}",
    response_class=HTMLResponse,
)
async def view_project_winner_slips(
    request: Request,
    project_id: int,
    only_lucky_draw: bool = Query(False),
):
    token = get_access_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")

    data = await fetch_project_print_data(project_id, token)
    # lọc bốc thăm nếu muốn (A cũng có param only_lucky_draw, nhưng mình lọc thêm cho chắc)
    items: List[Dict[str, Any]] = data.get("items") or []
    if only_lucky_draw:
        items = [x for x in items if x.get("is_lucky_draw") is True]

    return templates.TemplateResponse(
        "auction/winner_slips_project.html",
        {
            "request": request,
            "data": data,
            "project": data.get("project") or {},
            "items": items,
            "total": len(items),
            "only_lucky_draw": only_lucky_draw,
        },
    )

from fastapi.responses import RedirectResponse

# =========================================================
# ALIAS ROUTES (để khớp link UI: /auction/results/print...)
# Không ảnh hưởng routes cũ.
# =========================================================

@router.get("/auction/results/print", response_class=HTMLResponse)
async def view_winner_slip_alias(
    request: Request,
    project_id: int = Query(...),
    lot_code: str = Query(...),
):
    # Gọi lại handler cũ để giữ logic 1 nơi
    return await view_winner_slip(request=request, project_id=project_id, lot_code=lot_code)


@router.get("/auction/results/print-all", response_class=HTMLResponse)
async def view_project_winner_slips_alias(
    request: Request,
    project_id: int = Query(...),
    only_lucky_draw: bool = Query(False),
):
    return await view_project_winner_slips(
        request=request,
        project_id=project_id,
        only_lucky_draw=only_lucky_draw,
    )
