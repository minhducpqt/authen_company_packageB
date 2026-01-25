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
    # giữ query-string nếu có (đỡ mất filter)
    if request.url.query:
        nxt = quote(f"{request.url.path}?{request.url.query}")
    return RedirectResponse(url=f"/login?next={nxt}", status_code=303)

async def _put_json(path: str, token: str, payload: Dict[str, Any]):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ PUT {url} body={_preview_body(payload)}")
    async with httpx.AsyncClient(timeout=120.0) as c:
        try:
            r = await c.put(url, headers=headers, json=payload)
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
    IMPORTANT:
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
        "status": status,
    }
    return templates.TemplateResponse("auction_session/index.html", ctx)


@router.get("/auction/sessions/{session_id}", response_class=HTMLResponse)
async def auction_session_detail_page(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: Optional[int] = Query(None, ge=1),
):
    """
    Trang phiên cụ thể (FIX):
      - Nếu session đang DRAFT hoặc current_round_no = 0
        => AUTO gọi START để tạo Round 1 + snapshot lots/participants
      - Sau đó render UI theo round_no (query) hoặc current_round_no (fallback)
    """
    token = get_access_token(request)
    if not token:
        return _redirect_login(request)

    # 1) Load session
    st_s, sess = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}", token, None)
    if st_s != 200 or not isinstance(sess, dict):
        code = st_s if st_s in (401, 403, 404) else 502
        return templates.TemplateResponse(
            "auction_session/session.html",
            {"request": request, "title": "Phiên đấu", "error": {"status": st_s, "body": sess}},
            status_code=code,
        )

    sess_data = (sess.get("data") or sess) if isinstance(sess, dict) else {}
    sess_status = (sess_data.get("status") or "").upper()

    # 2) Load current round
    st_c, cur = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}/current", token, None)
    current_round_no = 0
    if st_c == 200 and isinstance(cur, dict):
        try:
            current_round_no = int(cur.get("current_round_no") or 0)
        except Exception:
            current_round_no = 0

    # 3) AUTO START nếu đang DRAFT hoặc chưa có round (current_round_no=0)
    #    Mục tiêu: tránh lỗi 404 khi gọi /rounds/1/ui
    if sess_status == "DRAFT" or current_round_no == 0:
        st_start, js_start = await _post_json(
            "/api/v1/auction-sessions/sessions/start",
            token,
            {"session_id": session_id},
        )

        # Nếu start fail vì reason nào đó, vẫn render với error rõ ràng
        # (nhưng cố reload current để lấy round_no nếu start đã thành công)
        st_c2, cur2 = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}/current", token, None)
        if st_c2 == 200 and isinstance(cur2, dict):
            try:
                current_round_no = int(cur2.get("current_round_no") or 0)
            except Exception:
                current_round_no = current_round_no or 0

        # reload session status (optional but helps UI show OPEN)
        st_s2, sess2 = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}", token, None)
        if st_s2 == 200 and isinstance(sess2, dict):
            sess_data = (sess2.get("data") or sess2) if isinstance(sess2, dict) else sess_data

        # Nếu vẫn không có round => báo lỗi start
        if current_round_no == 0:
            return templates.TemplateResponse(
                "auction_session/session.html",
                {
                    "request": request,
                    "title": f"Phiên đấu #{session_id}",
                    "session_id": session_id,
                    "session": sess_data,
                    "round_no": 1,
                    "rounds": [],
                    "ui": {"ok": False, "lots": []},
                    "error": {
                        "status": st_start,
                        "body": js_start,
                    },
                },
                status_code=502 if st_start not in (401, 403, 404) else st_start,
            )

    # 4) Chọn round_no để render:
    #    - ưu tiên round_no từ query
    #    - fallback = current_round_no
    #    - cuối cùng fallback = 1
    if not round_no or int(round_no) <= 0:
        round_no = current_round_no if current_round_no > 0 else 1

    # 5) Load UI round
    st_ui, ui = await _get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/{int(round_no)}/ui",
        token,
        None,
    )
    error: Optional[Dict[str, Any]] = None
    if st_ui != 200 or not isinstance(ui, dict):
        error = {"status": st_ui, "body": ui}
        ui = {"ok": False, "lots": []}

    # 6) Load rounds list
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
    NOTE (newest A):
      - winning_price/highest_price_vnd is "unit price" (PER_SQM or PER_LOT) per bid_price_unit.
      - results endpoint now returns bid_price_unit (also stored in results.extras).
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
    """
    Newest A:
      - returns r.* plus bid_price_unit (derived from r.extras->>'bid_price_unit')
    """
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}/results", token, None)
    return JSONResponse(js, status_code=_proxy_status(st))

# =========================================================
# EXTRA PROXIES (B -> A)
# - Session status update
# - Backfill participants.stt
# =========================================================

@router.post("/auction/sessions/api/sessions/{session_id}/status")
async def api_update_session_status(
    request: Request,
    session_id: int = Path(..., ge=1),
    payload: Dict[str, Any] = Body(...),
):
    """
    Proxy to Service A:
      POST /api/v1/auction-sessions/sessions/{session_id}/status

    payload (A: SessionUpdateStatusIn):
      {
        "status": "DRAFT" | "OPEN" | "PAUSED" | "CLOSED",
        "note": "optional"
      }
    """
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _post_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/status",
        token,
        payload,
    )
    return JSONResponse(js, status_code=_proxy_status(st))


@router.post("/auction/sessions/api/sessions/{session_id}/backfill-stt")
async def api_backfill_session_stt(
    request: Request,
    session_id: int = Path(..., ge=1),
):
    """
    Proxy to Service A:
      POST /api/v1/auction-sessions/sessions/{session_id}/backfill-stt

    No payload required.
    """
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _post_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/backfill-stt",
        token,
        {},
    )
    return JSONResponse(js, status_code=_proxy_status(st))

@router.put("/auction/sessions/api/sessions/{session_id}")
async def api_update_session(
    request: Request,
    session_id: int = Path(..., ge=1),
    payload: Dict[str, Any] = Body(...),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _put_json(f"/api/v1/auction-sessions/sessions/{session_id}", token, payload)
    return JSONResponse(js, status_code=_proxy_status(st))

# =========================================================
# NEW: Attendance list (per session) + refund bank snapshot
# - Returns: full session info + derived stats + attendance list sorted by stt
# - Refund bank accounts: take from first participant snapshot seen for that customer
#   (because snapshot stored per (customer_id, lot_id) but is same across pairs)
# =========================================================
@router.get("/auction/sessions/api/sessions/{session_id}/attendance")
async def api_session_attendance(
    request: Request,
    session_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    # 1) Load session detail (for project_name + session meta)
    st_s, sess = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}", token, None)
    if st_s != 200 or not isinstance(sess, dict):
        return JSONResponse(sess, status_code=_proxy_status(st_s))

    sess_data = (sess.get("data") or sess) if isinstance(sess, dict) else {}
    project_name = sess_data.get("project_name") or sess_data.get("p_project_name")  # safe fallback
    project_code = sess_data.get("project_code") or sess_data.get("p_project_code")

    # 2) Determine a round_no to pull UI from (prefer current -> fallback 1)
    st_c, cur = await _get_json(f"/api/v1/auction-sessions/sessions/{session_id}/current", token, None)
    round_no = 1
    if st_c == 200 and isinstance(cur, dict):
        try:
            rn = int(cur.get("current_round_no") or 0)
            round_no = rn if rn > 0 else 1
        except Exception:
            round_no = 1

    # 3) Load round UI (contains lots + participants snapshots)
    st_ui, ui = await _get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/{int(round_no)}/ui",
        token,
        None,
    )
    if st_ui != 200 or not isinstance(ui, dict):
        return JSONResponse(
            {"ok": False, "error": {"status": st_ui, "body": ui}},
            status_code=_proxy_status(st_ui),
        )

    lots = ui.get("lots") or []
    lot_count = len(lots)

    # 4) Build attendance aggregated by customer_id
    # - customer snapshot from p.extras.snapshot OR p.customer_snapshot (already added by A)
    # - refund snapshot from p.extras.refund_bank_accounts (your new data)
    # - lot_count per customer = distinct lot_id count across participants
    by_cid: Dict[int, Dict[str, Any]] = {}
    lotset_by_cid: Dict[int, set] = {}

    for lot in lots:
        lot_id = lot.get("lot_id")
        parts = lot.get("participants") or []
        for p in parts:
            cid_raw = p.get("customer_id")
            if cid_raw is None:
                continue
            try:
                cid = int(cid_raw)
                if cid <= 0:
                    continue
            except Exception:
                continue

            # initialize
            if cid not in by_cid:
                by_cid[cid] = {
                    "customer_id": cid,
                    "stt": p.get("stt"),
                    "customer": None,
                    "refund_bank_accounts": None,
                }
                lotset_by_cid[cid] = set()

            # lot count
            try:
                if lot_id is not None:
                    lotset_by_cid[cid].add(int(lot_id))
            except Exception:
                pass

            # customer snapshot priority:
            #  - A returns "customer_snapshot" alias (SELECT (p.extras->'snapshot') AS customer_snapshot)
            #  - or nested extras.snapshot
            snap = p.get("customer_snapshot")
            if snap is None:
                extras = p.get("extras") if isinstance(p.get("extras"), dict) else None
                if extras and isinstance(extras.get("snapshot"), dict):
                    snap = extras.get("snapshot")

            if by_cid[cid]["customer"] is None and isinstance(snap, dict):
                by_cid[cid]["customer"] = snap

            # refund snapshot: p.extras.refund_bank_accounts (take the first one seen)
            if by_cid[cid]["refund_bank_accounts"] is None:
                extras = p.get("extras") if isinstance(p.get("extras"), dict) else None
                if extras is not None:
                    rba = extras.get("refund_bank_accounts")
                    if rba is not None:
                        by_cid[cid]["refund_bank_accounts"] = rba

            # stt: keep the smallest non-null (safe)
            stt0 = by_cid[cid].get("stt")
            stt1 = p.get("stt")
            try:
                if stt0 is None and stt1 is not None:
                    by_cid[cid]["stt"] = int(stt1)
                elif stt0 is not None and stt1 is not None:
                    by_cid[cid]["stt"] = min(int(stt0), int(stt1))
            except Exception:
                pass

    # finalize list
    data: List[Dict[str, Any]] = []
    for cid, item in by_cid.items():
        lots_of_c = lotset_by_cid.get(cid) or set()
        item["lot_count"] = len(lots_of_c)
        # optional: include lot_ids for debugging / export
        # item["lot_ids"] = sorted(list(lots_of_c))
        data.append(item)

    # sort by stt ASC, nulls last, then customer_id
    def _sort_key(x: Dict[str, Any]):
        stt = x.get("stt")
        try:
            stt_int = int(stt)
            return (0, stt_int, int(x.get("customer_id") or 0))
        except Exception:
            return (1, 10**18, int(x.get("customer_id") or 0))

    data.sort(key=_sort_key)
    customer_count = len(data)

    out = {
        "ok": True,
        "session": {
            "id": sess_data.get("id") or session_id,
            "name": sess_data.get("name"),
            "status": sess_data.get("status"),
            "auction_date": sess_data.get("auction_date"),
            "location": sess_data.get("location"),
            "province": sess_data.get("province"),
            "district": sess_data.get("district"),
            "venue": sess_data.get("venue"),
            "note": sess_data.get("note"),
            "project_id": sess_data.get("project_id"),
            "project_code": project_code,
            "project_name": project_name,
            "lot_count": lot_count,
            "customer_count": customer_count,
            "round_no": int(round_no),
        },
        "data": data,
    }
    return JSONResponse(out, status_code=200)

# =========================================================
# Wiring note (Service B)
# - Add to your main/app include_router area:
#     from routers.auction_sessions import router as auction_sessions_router
#     app.include_router(auction_sessions_router)
# =========================================================
