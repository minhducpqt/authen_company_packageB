# routers/auction_sessions.py  (Service B - Admin Portal)
from __future__ import annotations

import os
from typing import Optional, Dict, Any, List, Tuple

import httpx
from fastapi import APIRouter, Request, Query, Path, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from urllib.parse import quote

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction_sessions"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# =========================================================
# Helpers
# =========================================================
def _log(msg: str):
    print(f"[AUCTION_SESS_B] {msg}")


_SENSITIVE_KEYS = {
    "phone",
    "cccd",
    "id_no",
    "identity_no",
    "email",
    "bank_account",
    "account_no",
    "card_no",
    "token",
    "access_token",
    "authorization",
}


def _mask_value(v: Any) -> Any:
    try:
        s = str(v)
    except Exception:
        return "***"
    if len(s) <= 4:
        return "***"
    return s[:2] + "***" + s[-2:]


def _sanitize(obj: Any) -> Any:
    # mask sensitive keys in nested dict/list
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in _SENSITIVE_KEYS:
                out[k] = _mask_value(v)
            else:
                out[k] = _sanitize(v)
        return out
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    return obj


def _preview_body(data: Any, limit: int = 320) -> str:
    try:
        import json

        safe = _sanitize(data)
        s = json.dumps(safe, ensure_ascii=False, default=str)
    except Exception:
        try:
            s = str(data)
        except Exception:
            s = "<unprintable>"
    return s if len(s) <= limit else s[:limit] + "...(truncated)"


def _unauth_json():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


def _redirect_login(request: Request) -> RedirectResponse:
    # quay lại đúng path hiện tại
    nxt = quote(request.url.path)
    return RedirectResponse(url=f"/login?next={nxt}", status_code=303)


async def _get_json(
    path: str,
    token: str,
    params: Dict[str, Any] | List[Tuple[str, Any]] | None = None,
):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ GET {url} params={params or {}}")
    async with httpx.AsyncClient(timeout=60.0) as c:
        try:
            r = await c.get(url, headers=headers, params=params or {})
        except Exception as e:
            _log(f"← EXC {url} error={e}")
            return 599, {"detail": str(e)}

    try:
        js = r.json()
        _log(f"← {r.status_code} {url} json={_preview_body(js)}")
        return r.status_code, js
    except Exception:
        body = (r.text or "")[:500]
        _log(f"← {r.status_code} {url} non-json body={body}")
        return r.status_code, {"detail": body}


async def _post_json(path: str, token: str, payload: Dict[str, Any]):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ POST {url} body={_preview_body(payload)}")
    async with httpx.AsyncClient(timeout=120.0) as c:
        try:
            r = await c.post(url, headers=headers, json=payload)
        except Exception as e:
            _log(f"← EXC {url} error={e}")
            return 599, {"detail": str(e)}

    try:
        js = r.json()
        _log(f"← {r.status_code} {url} json={_preview_body(js)}")
        return r.status_code, js
    except Exception:
        body = (r.text or "")[:500]
        _log(f"← {r.status_code} {url} non-json body={body}")
        return r.status_code, {"detail": body}


async def _load_projects(
    token: str,
    project_param: Optional[str],
    status_param: Optional[str],
) -> tuple[list[dict], str, Optional[dict]]:
    """
    IMPORTANT CHANGE:
    - Không hardcode ACTIVE.
    - Nếu status_param is None/"" => KHÔNG truyền status => lấy FULL.
    - Nếu có status_param => truyền đúng sang Service A.
    """
    params: Dict[str, Any] = {"size": 1000}
    if status_param:
        params["status"] = status_param

    st, pj = await _get_json("/api/v1/projects", token, params)
    projects: list[dict] = []
    selected_code = (project_param or "").strip().upper()
    selected_project: Optional[dict] = None

    if st == 200 and isinstance(pj, dict):
        projects = pj.get("data") or pj.get("items") or []
        if not selected_code and len(projects) == 1:
            selected_code = (projects[0].get("project_code") or projects[0].get("code") or "").strip().upper()

        if selected_code:
            for p in projects:
                code = (p.get("project_code") or p.get("code") or "").strip().upper()
                if code == selected_code:
                    selected_project = p
                    break

    return projects, selected_code, selected_project


def _project_id_of(p: Optional[dict]) -> Optional[int]:
    if not p:
        return None
    for k in ("id", "project_id"):
        v = p.get(k)
        if v is not None:
            try:
                iv = int(v)
                if iv > 0:
                    return iv
            except Exception:
                pass
    return None


# =========================================================
# Pages (SSR)
# =========================================================
@router.get("/auction/sessions", response_class=HTMLResponse)
async def auction_sessions_page(
    request: Request,
    project: Optional[str] = Query(None),
    status: Optional[str] = Query(
        None,
        description="Project status filter. If omitted -> fetch FULL projects (no status param).",
    ),
):
    """
    Trang điều phối:
      - chọn dự án
      - auto show phiên dở dang (primary) + list candidates
      - có nút tạo phiên mới / start phiên / tiếp tục
    """
    token = get_access_token(request)
    if not token:
        return _redirect_login(request)

    projects, selected_code, selected_project = await _load_projects(token, project, status)
    project_id = _project_id_of(selected_project)

    active: Dict[str, Any] = {"has_active": False, "primary_session": None, "candidates": []}
    error: Optional[Dict[str, Any]] = None

    if project_id:
        st, js = await _get_json(f"/api/v1/auction-sessions/projects/{project_id}/active", token, None)
        if st == 200 and isinstance(js, dict):
            active = js
        else:
            error = {"status": st, "body": js}

    ctx = {
        "request": request,
        "title": "Vận hành phiên đấu",
        "projects": projects,
        "project": selected_code,
        "project_obj": selected_project,
        "project_id": project_id,
        "active": active,
        "error": error,
        "status": status,  # để template giữ filter nếu muốn
    }
    return templates.TemplateResponse("auction_session/index.html", ctx)


@router.get("/auction/sessions/{session_id}", response_class=HTMLResponse)
async def auction_session_detail_page(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: Optional[int] = Query(None, ge=1),
):
    """
    Trang phiên cụ thể:
      - load current round nếu round_no không truyền
      - gọi /rounds/{round_no}/ui để render danh sách lô + khách
    """
    token = get_access_token(request)
    if not token:
        return _redirect_login(request)

    st_s, sess = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}", token, None)
    if st_s != 200 or not isinstance(sess, dict):
        # trả 404/403/401 nếu upstream trả vậy; còn lại coi là upstream error
        code = st_s if st_s in (401, 403, 404) else 502
        return templates.TemplateResponse(
            "auction_session/session.html",
            {"request": request, "title": "Phiên đấu", "error": {"status": st_s, "body": sess}},
            status_code=code,
        )

    sess_data = (sess.get("data") or sess) if isinstance(sess, dict) else {}

    if not round_no:
        st_c, cur = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}/current", token, None)
        if st_c == 200 and isinstance(cur, dict):
            try:
                round_no = int(cur.get("current_round_no") or 1)
            except Exception:
                round_no = 1
        else:
            round_no = 1

    st_ui, ui = await _get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/{int(round_no)}/ui",
        token,
        None,
    )
    error: Optional[Dict[str, Any]] = None
    if st_ui != 200 or not isinstance(ui, dict):
        error = {"status": st_ui, "body": ui}
        ui = {"ok": False, "lots": []}

    st_r, rounds = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}/rounds", token, None)
    rounds_data = rounds.get("data") if (st_r == 200 and isinstance(rounds, dict)) else []

    ctx = {
        "request": request,
        "title": f"Phiên đấu #{session_id}",
        "session_id": session_id,
        "session": sess_data,
        "round_no": int(round_no),
        "rounds": rounds_data,
        "ui": ui,
        "error": error,
    }
    return templates.TemplateResponse("auction_session/session.html", ctx)


# =========================================================
# AJAX APIs (Service B -> proxy to Service A)
# - IMPORTANT: pass-through status codes
# =========================================================
def _proxy_status(st: int) -> int:
    # network / local exception
    if st == 599:
        return 503
    return st


@router.get("/auction/sessions/api/projects/{project_id}/active")
async def api_project_active_session(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _get_json(f"/api/v1/auction-sessions/projects/{project_id}/active", token, None)
    return JSONResponse(js, status_code=_proxy_status(st))


@router.get("/auction/sessions/api/sessions")
async def api_list_sessions(
    request: Request,
    project_id: Optional[int] = Query(None, ge=1),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    params: Dict[str, Any] = {"page": page, "size": size}
    if project_id:
        params["project_id"] = project_id
    if status:
        params["status"] = status

    st, js = await _get_json("/api/v1/auction-sessions/sessions", token, params)
    return JSONResponse(js, status_code=_proxy_status(st))


@router.post("/auction/sessions/api/sessions")
async def api_create_session(
    request: Request,
    payload: Dict[str, Any] = Body(...),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _post_json("/api/v1/auction-sessions/sessions", token, payload)
    return JSONResponse(js, status_code=_proxy_status(st))


@router.post("/auction/sessions/api/sessions/start")
async def api_start_session(
    request: Request,
    payload: Dict[str, Any] = Body(...),
):
    """
    payload: { session_id: number }
    """
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _post_json("/api/v1/auction-sessions/sessions/start", token, payload)
    return JSONResponse(js, status_code=_proxy_status(st))


@router.get("/auction/sessions/api/sessions/{session_id}/rounds")
async def api_list_rounds(
    request: Request,
    session_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}/rounds", token, None)
    return JSONResponse(js, status_code=_proxy_status(st))


@router.get("/auction/sessions/api/sessions/{session_id}/current")
async def api_current_round(
    request: Request,
    session_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}/current", token, None)
    return JSONResponse(js, status_code=_proxy_status(st))


@router.get("/auction/sessions/api/sessions/{session_id}/rounds/{round_no}/ui")
async def api_round_ui(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}/ui",
        token,
        None,
    )
    return JSONResponse(js, status_code=_proxy_status(st))


@router.post("/auction/sessions/api/round-lots/{round_lot_id}/lock")
async def api_lock_round_lot(
    request: Request,
    round_lot_id: int = Path(..., ge=1),
    payload: Dict[str, Any] = Body(...),
):
    """
    payload: { ttl_seconds: 900 }
    """
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _post_json(f"/api/v1/auction-sessions/round-lots/{round_lot_id}/lock", token, payload)
    return JSONResponse(js, status_code=_proxy_status(st))


@router.post("/auction/sessions/api/round-lots/{round_lot_id}/unlock")
async def api_unlock_round_lot(
    request: Request,
    round_lot_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _post_json(f"/api/v1/auction-sessions/round-lots/{round_lot_id}/unlock", token, {})
    return JSONResponse(js, status_code=_proxy_status(st))


@router.post("/auction/sessions/api/round-lots/{round_lot_id}/decide")
async def api_decide_round_lot(
    request: Request,
    round_lot_id: int = Path(..., ge=1),
    payload: Dict[str, Any] = Body(...),
):
    """
    payload same as Service A DecideIn:
      - result_type: PENDING|WINNER|NEXT_ROUND|NO_VALID
      - win_method: HIGHEST|LOTTERY|MANUAL
      - winner_customer_id?
      - highest_price_vnd?
      - next_customer_ids?
      - note?
      - extras?
      - client_updated_at?
    """
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _post_json(f"/api/v1/auction-sessions/round-lots/{round_lot_id}/decide", token, payload)
    return JSONResponse(js, status_code=_proxy_status(st))


@router.post("/auction/sessions/api/sessions/{session_id}/rounds/next")
async def api_create_next_round(
    request: Request,
    session_id: int = Path(..., ge=1),
    payload: Dict[str, Any] = Body(...),
):
    """
    payload:
      { session_id, from_round_no, note? }
    """
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _post_json(f"/api/v1/auction-sessions/sessions/{session_id}/rounds/next", token, payload)
    return JSONResponse(js, status_code=_proxy_status(st))


@router.get("/auction/sessions/api/sessions/{session_id}/results")
async def api_list_session_results(
    request: Request,
    session_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}/results", token, None)
    return JSONResponse(js, status_code=_proxy_status(st))


# =========================================================
# Wiring note (Service B)
# - Add to your main/app include_router area:
#     from routers.auction_sessions import router as auction_sessions_router
#     app.include_router(auction_sessions_router)
# =========================================================
