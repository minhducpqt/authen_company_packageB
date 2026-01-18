from __future__ import annotations

import os
from typing import Optional, Dict, Any, List, Tuple

import httpx
from fastapi import APIRouter, Request, Query, Path, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction_counting"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


def _log(msg: str):
    print(f"[AUCTION_COUNTING_B] {msg}")


def _preview_body(data: Any, limit: int = 300) -> str:
    try:
        import json
        s = json.dumps(data, ensure_ascii=False)
    except Exception:
        s = str(data)
    return s if len(s) <= limit else s[:limit] + "...(truncated)"


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
        return r.status_code, {"detail": (r.text or "")[:500]}


async def _post_json(path: str, token: str, payload: Dict[str, Any] | None = None):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    body = payload or {}
    _log(f"→ POST {url} body={_preview_body(body)}")
    async with httpx.AsyncClient(timeout=120.0) as c:
        try:
            r = await c.post(url, headers=headers, json=body)
        except Exception as e:
            _log(f"← EXC {url} error={e}")
            return 599, {"detail": str(e)}
    try:
        js = r.json()
        _log(f"← {r.status_code} {url} json={_preview_body(js)}")
        return r.status_code, js
    except Exception:
        return r.status_code, {"detail": (r.text or "")[:500]}


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
        return r.status_code, {"detail": (r.text or "")[:500]}


def _unauth_json():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


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


async def _load_projects_all(token: str, project_param: Optional[str]) -> tuple[list[dict], str, Optional[dict], list[dict]]:
    """
    - dropdown: ALL projects (active + inactive)
    - auto-select: if user not pick AND only 1 ACTIVE project exists → auto pick that ACTIVE.
    - project_param can be project_code (string) or project_id (number string); we try both.
    Return: (all_projects, selected_key, selected_project, active_projects)
    """
    st_all, js_all = await _get_json("/api/v1/projects", token, {"size": 1000})
    st_act, js_act = await _get_json("/api/v1/projects", token, {"status": "ACTIVE", "size": 1000})

    all_projects: list[dict] = []
    active_projects: list[dict] = []
    if st_all == 200 and isinstance(js_all, dict):
        all_projects = js_all.get("data") or js_all.get("items") or []
    if st_act == 200 and isinstance(js_act, dict):
        active_projects = js_act.get("data") or js_act.get("items") or []

    selected = (project_param or "").strip()
    selected_project: Optional[dict] = None

    # auto-select if only 1 ACTIVE
    if not selected and len(active_projects) == 1:
        p0 = active_projects[0]
        selected = str((p0.get("project_code") or p0.get("code") or p0.get("id") or "")).strip()

    # try match by project_code first
    sel_upper = selected.upper()
    if selected:
        for p in all_projects:
            code = str((p.get("project_code") or p.get("code") or "")).strip()
            if code and code.upper() == sel_upper:
                selected_project = p
                break

    # fallback match by id
    if selected and not selected_project:
        try:
            sel_id = int(selected)
        except Exception:
            sel_id = None
        if sel_id:
            for p in all_projects:
                pid = _project_id_of(p)
                if pid == sel_id:
                    selected_project = p
                    break

    return all_projects, selected, selected_project, active_projects


# =========================================================
# SSR PAGE - ADMIN COUNTING (2 rounds)
# =========================================================
@router.get("/auction/counting", response_class=HTMLResponse)
async def auction_counting_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code or project_id"),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=500),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fauction%2Fcounting", status_code=303)

    projects, selected_key, selected_project, active_projects = await _load_projects_all(token, project)
    project_id = _project_id_of(selected_project)

    # ensure a COUNTING session exists if project selected
    session: Optional[Dict[str, Any]] = None
    session_err: Optional[Dict[str, Any]] = None
    if project_id:
        st, js = await _post_json(f"/api/v1/auction-counting/projects/{project_id}/sessions/start", token, {})
        if st == 200 and isinstance(js, dict):
            session = js.get("session")
        else:
            session_err = {"status": st, "body": js}

    # initial lots list
    data: Dict[str, Any] = {"data": [], "total": 0, "page": page, "size": size, "project": None, "session": session}
    error: Optional[Dict[str, Any]] = None

    if project_id and session and session.get("id"):
        params: Dict[str, Any] = {"page": page, "size": size, "session_id": session["id"]}
        if q:
            params["q"] = q
        st, js = await _get_json(f"/api/v1/auction-counting/projects/{project_id}/lots", token, params)
        if st == 200 and isinstance(js, dict):
            data = js
        else:
            error = {"status": st, "body": js}

    ctx = {
        "request": request,
        "title": "Kiểm phiếu trúng đấu giá",
        "projects": projects,
        "active_projects": active_projects,
        "project": selected_key,
        "project_obj": selected_project,
        "project_id": project_id,
        "q": q or "",
        "page": page,
        "size": size,
        "data": data,
        "error": error,
        "session": session,
        "session_err": session_err,
    }
    return templates.TemplateResponse("auction/auction_counting.html", ctx)


# =========================================================
# SSR PAGE - DISPLAY (PROJECTOR)
# =========================================================
@router.get("/auction/counting/display", response_class=HTMLResponse)
async def auction_counting_display_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code or project_id"),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fauction%2Fcounting%2Fdisplay", status_code=303)

    projects, selected_key, selected_project, active_projects = await _load_projects_all(token, project)
    project_id = _project_id_of(selected_project)

    ctx = {
        "request": request,
        "title": "Trình chiếu kiểm phiếu",
        "projects": projects,
        "active_projects": active_projects,
        "project": selected_key,
        "project_obj": selected_project,
        "project_id": project_id,
        "poll_ms": 2000,  # mượt hơn (2s)
    }
    return templates.TemplateResponse("auction/auction_counting_display.html", ctx)


# =========================================================
# AJAX APIs (proxy to Service A)
# =========================================================
@router.post("/auction/counting/api/projects/{project_id}/sessions/start")
async def api_start_session(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()
    st, js = await _post_json(f"/api/v1/auction-counting/projects/{project_id}/sessions/start", token, {})
    return JSONResponse(js, status_code=200 if st == 200 else 502)


@router.get("/auction/counting/api/projects/{project_id}/sessions/current")
async def api_current_session(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()
    st, js = await _get_json(f"/api/v1/auction-counting/projects/{project_id}/sessions/current", token, {})
    return JSONResponse(js, status_code=200 if st == 200 else 502)


@router.get("/auction/counting/api/projects/{project_id}/lots")
async def api_list_lots(
    request: Request,
    project_id: int = Path(..., ge=1),
    session_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=500),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    params: Dict[str, Any] = {"page": page, "size": size}
    if session_id:
        params["session_id"] = session_id
    if q:
        params["q"] = q

    st, js = await _get_json(f"/api/v1/auction-counting/projects/{project_id}/lots", token, params)
    return JSONResponse(js, status_code=200 if st == 200 else 502)


@router.get("/auction/counting/api/projects/{project_id}/lots/{lot_code}/eligible-customers")
async def api_eligible_customers(
    request: Request,
    project_id: int = Path(..., ge=1),
    lot_code: str = Path(..., min_length=1),
    include_unpaid: bool = Query(False),
    limit: int = Query(5000, ge=1, le=5000),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    params: Dict[str, Any] = {"limit": limit, "include_unpaid": include_unpaid}
    st, js = await _get_json(
        f"/api/v1/auction-counting/projects/{project_id}/lots/{lot_code}/eligible-customers",
        token,
        params,
    )
    return JSONResponse(js, status_code=200 if st == 200 else 502)


@router.put("/auction/counting/api/sessions/{session_id}/lots/{lot_code}")
async def api_upsert_counting_lot(
    request: Request,
    session_id: int = Path(..., ge=1),
    lot_code: str = Path(..., min_length=1),
    payload: Dict[str, Any] = Body(...),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _put_json(f"/api/v1/auction-counting/sessions/{session_id}/lots/{lot_code}", token, payload)
    return JSONResponse(js, status_code=200 if st == 200 else 502)


@router.get("/auction/counting/api/display/snapshot")
async def api_display_snapshot(
    request: Request,
    project_id: int = Query(..., ge=1),
    session_id: Optional[int] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    params: Dict[str, Any] = {"project_id": project_id}
    if session_id:
        params["session_id"] = session_id

    st, js = await _get_json("/api/v1/auction-counting/display/snapshot", token, params)
    return JSONResponse(js, status_code=200 if st == 200 else 502)
