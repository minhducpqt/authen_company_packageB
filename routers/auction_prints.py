# app/routers/auction_prints.py
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional, List

import httpx
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import HTMLResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction:prints"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824").rstrip("/")

# Bật/tắt debug tùy bạn. Nếu bạn muốn luôn log raw thì để "1".
AUCTION_PRINT_DEBUG = os.getenv("AUCTION_PRINT_DEBUG", "1").strip().lower() in ("1", "true", "yes", "on")

# chunk nhỏ để journald không cắt 1 dòng quá dài
_LOG_CHUNK = int(os.getenv("AUCTION_PRINT_LOG_CHUNK", "3500"))


# ---------------- Logging helpers ----------------
def _log(msg: str) -> None:
    print(f"[AUCTION_PRINTS_B] {msg}")


def _log_big(title: str, text: str) -> None:
    """
    In nội dung dài theo nhiều dòng để tránh journald/systemd cắt cụt.
    """
    if text is None:
        _log(f"{title}: <None>")
        return

    s = str(text)
    if not s:
        _log(f"{title}: <empty>")
        return

    _log(f"{title}: len={len(s)}")
    # in theo chunk
    for i in range(0, len(s), _LOG_CHUNK):
        _log(s[i : i + _LOG_CHUNK])


def _pretty_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False, default=str)
    except Exception:
        # fallback: string
        return str(obj)


# ---------------- HTTP helpers ----------------
async def _get_json(path: str, token: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = SERVICE_A_BASE_URL + path
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    if AUCTION_PRINT_DEBUG:
        _log(f"→ GET {url} params={params or {}}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers=headers, params=params or {})

        if AUCTION_PRINT_DEBUG:
            _log(f"← {r.status_code} {url}")

        # Nếu lỗi: in raw body đầy đủ luôn
        if r.status_code >= 400:
            raw = r.text or ""
            if AUCTION_PRINT_DEBUG:
                _log_big("A ERROR RAW BODY", raw)
                # thử parse json cho dễ đọc
                try:
                    js = r.json()
                    _log_big("A ERROR JSON PRETTY", _pretty_json(js))
                except Exception:
                    pass

            raise HTTPException(
                status_code=r.status_code,
                detail=f"Service A error {r.status_code} on GET {path}",
            )

        # Thành công: parse json + log full pretty + raw (nếu muốn)
        try:
            js = r.json()
        except Exception:
            raw = r.text or ""
            if AUCTION_PRINT_DEBUG:
                _log_big("A OK RAW (NOT JSON)", raw)
            raise HTTPException(status_code=502, detail="Service A returned non-JSON response")

        if AUCTION_PRINT_DEBUG:
            _log_big("A OK JSON PRETTY", _pretty_json(js))

        return js


# ---------------- A APIs (print-data) ----------------
async def fetch_project_print_data(project_id: int, token: str, only_lucky_draw: bool = False) -> Dict[str, Any]:
    # A endpoint hiện tại của bạn không bắt buộc param, nhưng hỗ trợ thì truyền luôn
    params = {"only_lucky_draw": "true"} if only_lucky_draw else {}
    return await _get_json(f"/api/v1/auction-results/print/projects/{project_id}", token, params=params)


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
        raise HTTPException(status_code=401, detail="Not logged in")

    _log(f"hit view_winner_slip project_id={project_id} lot_code={lot_code}")

    data = await fetch_lot_print_data(project_id, lot_code, token)

    # log thêm các key quan trọng (để biết B đang nhìn gì)
    if AUCTION_PRINT_DEBUG:
        try:
            _log(f"keys(data)={list((data or {}).keys())}")
            proj = (data or {}).get("project") or {}
            win = (data or {}).get("winner") or {}
            lot = (win or {}).get("lot") or {}
            _log(f"keys(project)={list(proj.keys())}")
            _log(f"keys(winner)={list(win.keys())}")
            _log(f"keys(winner.lot)={list(lot.keys())}")
        except Exception:
            pass

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

    _log(f"hit view_project_winner_slips project_id={project_id} only_lucky_draw={only_lucky_draw}")

    data = await fetch_project_print_data(project_id, token, only_lucky_draw=only_lucky_draw)

    items: List[Dict[str, Any]] = data.get("items") or []
    if only_lucky_draw:
        items = [x for x in items if x.get("is_lucky_draw") is True]

    if AUCTION_PRINT_DEBUG:
        _log(f"total items after filter = {len(items)}")

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


# =========================================================
# ALIAS ROUTES (để khớp link UI: /auction/results/print...)
# =========================================================
@router.get("/auction/results/print", response_class=HTMLResponse)
async def view_winner_slip_alias(
    request: Request,
    project_id: int = Query(...),
    lot_code: str = Query(...),
):
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
