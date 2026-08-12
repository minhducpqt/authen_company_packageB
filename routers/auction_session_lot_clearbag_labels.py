# routers/auction_session_lot_clearbag_labels.py  (Service B - Admin Portal)
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.auth import fetch_me, get_access_token
from utils.templates import templates

router = APIRouter(
    prefix="/auction-sessions/lot-clearbag-labels",
    tags=["auction_session_lot_clearbag_labels"],
)

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824").rstrip("/")
PRINT_TEMPLATE_NORMAL = "pages/auction_session_documents/lot_clearbag_label_print.html"
PRINT_TEMPLATE_GROUP = "pages/auction_session_documents/lot_clearbag_label_print_group.html"


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    params: dict | None = None,
) -> Tuple[int, Any]:
    r = await client.get(url, headers=headers, params=params or {})
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None


async def _ensure_me_or_redirect(
    request: Request,
    next_path: str,
) -> Tuple[Optional[Dict[str, Any]], Union[str, RedirectResponse]]:
    token = get_access_token(request)
    me = await fetch_me(token) if token else None
    if not me:
        return None, RedirectResponse(url=f"/login?next={quote(next_path)}", status_code=303)
    return me, token


def _err_html(msg: str, code: int = 500) -> HTMLResponse:
    return HTMLResponse(f"<h1>Lỗi</h1><p>{msg}</p>", status_code=code)


def _pair_lots(lots: List[Dict[str, Any]]) -> List[Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]]:
    """NORMAL: 2 nhãn / trang A4 (trên–dưới)."""
    pages: List[Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]] = []
    for i in range(0, max(len(lots), 1), 2):
        left = lots[i] if i < len(lots) else None
        right = lots[i + 1] if i + 1 < len(lots) else None
        pages.append((left, right))
    if not pages:
        pages.append((None, None))
    return pages


def _quad_lots(lots: List[Dict[str, Any]]) -> List[List[Optional[Dict[str, Any]]]]:
    """GROUP: 4 nhãn / trang A4 (2×2)."""
    pages: List[List[Optional[Dict[str, Any]]]] = []
    n = max(len(lots), 1)
    for i in range(0, n, 4):
        chunk: List[Optional[Dict[str, Any]]] = []
        for j in range(4):
            idx = i + j
            chunk.append(lots[idx] if idx < len(lots) else None)
        pages.append(chunk)
    if not pages:
        pages.append([None, None, None, None])
    return pages


@router.get("/print/rounds/{round_id}", response_class=HTMLResponse)
async def print_lot_clearbag_labels_for_round(
    request: Request,
    round_id: int = Path(..., ge=1),
    autoprint: int = Query(0, ge=0, le=1),
):
    next_path = f"/auction-sessions/lot-clearbag-labels/print/rounds/{int(round_id)}"
    me, token_or_redirect = await _ensure_me_or_redirect(request, next_path)
    if isinstance(token_or_redirect, RedirectResponse):
        return token_or_redirect
    token = token_or_redirect

    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=60.0) as client:
            st, js = await _get_json(
                client,
                f"/api/v1/report/auction-sessions/rounds/{int(round_id)}/lot-clearbag-labels",
                headers,
            )
    except Exception as exc:
        return _err_html(str(exc), 500)

    if st != 200 or not isinstance(js, dict):
        detail = ""
        if isinstance(js, dict):
            detail = str(js.get("detail") or "")
        return _err_html(
            detail or f"Không lấy được dữ liệu nhãn clearbag (HTTP {st}).",
            404 if st == 404 else 500,
        )

    payload = js.get("data") if isinstance(js.get("data"), dict) else {}
    lots = payload.get("lots") if isinstance(payload.get("lots"), list) else []

    if not lots:
        return _err_html(
            "Vòng này chưa có dữ liệu lô để in nhãn. Vui lòng Start phiên hoặc kiểm tra lại vòng.",
            404,
        )

    registration_mode = str(payload.get("registration_mode") or "NORMAL").strip().upper()
    is_group = registration_mode == "GROUP_AUCTION"
    show_issued_count = payload.get("show_issued_count")
    if show_issued_count is None:
        show_issued_count = not is_group

    if is_group:
        pages = _quad_lots(lots)
        template = PRINT_TEMPLATE_GROUP
    else:
        pages = _pair_lots(lots)
        template = PRINT_TEMPLATE_NORMAL

    return templates.TemplateResponse(
        template,
        {
            "request": request,
            "me": me,
            "pages": pages,
            "session_id": payload.get("session_id"),
            "round_id": payload.get("round_id") or round_id,
            "round_no": payload.get("round_no"),
            "next_round_no": payload.get("next_round_no"),
            "project_code": payload.get("project_code") or "",
            "project_name": payload.get("project_name") or "",
            "registration_mode": registration_mode,
            "lot_policy": payload.get("lot_policy"),
            "show_issued_count": bool(show_issued_count),
            "total_lots": len(lots),
            "autoprint": int(autoprint),
        },
    )
