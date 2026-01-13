# routers/auction_results.py
from __future__ import annotations

import os
from typing import Optional, Dict, Any, List, Tuple

import httpx
from fastapi import APIRouter, Request, Query, Path, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction_results"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


def _log(msg: str):
    print(f"[AUCTION_53_B] {msg}")


def _preview_body(data: Any, limit: int = 300) -> str:
    try:
        import json
        s = json.dumps(data, ensure_ascii=False)
    except Exception:
        s = str(data)
    return s if len(s) <= limit else s[:limit] + "...(truncated)"


async def _get_json(path: str, token: str, params: Dict[str, Any] | List[Tuple[str, Any]] | None = None):
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


async def _put_json(path: str, token: str, payload: Dict[str, Any]):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ PUT {url} body={_preview_body(payload)}")
    async with httpx.AsyncClient(timeout=60.0) as c:
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
        return r.status_code, {"detail": (r.text or "")[:500]}


def _unauth_json():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


async def _load_projects(token: str, project_param: Optional[str]) -> tuple[list[dict], str, Optional[dict]]:
    st, pj = await _get_json("/api/v1/projects", token, {"status": "ACTIVE", "size": 1000})
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


# =========================
# SSR PAGE
# =========================
@router.get("/auction/results", response_class=HTMLResponse)
async def auction_results_page(
    request: Request,
    project: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    result_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=500),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fauction%2Fresults", status_code=303)

    projects, selected_code, selected_project = await _load_projects(token, project)
    project_id = _project_id_of(selected_project)

    data: Dict[str, Any] = {"data": [], "total": 0, "page": page, "size": size, "project": None}
    error: Optional[Dict[str, Any]] = None

    if project_id:
        params: Dict[str, Any] = {"page": page, "size": size}
        if q:
            params["q"] = q
        if result_status:
            params["result_status"] = result_status

        st, js = await _get_json(f"/api/v1/auction-results/projects/{project_id}/lots", token, params)
        if st == 200 and isinstance(js, dict):
            data = js
        else:
            error = {"status": st, "body": js}

    ctx = {
        "request": request,
        "title": "Trúng đấu giá",
        "projects": projects,
        "project": selected_code,
        "project_obj": selected_project,
        "project_id": project_id,
        "q": q or "",
        "result_status": (result_status or ""),
        "page": page,
        "size": size,
        "data": data,
        "error": error,
    }
    return templates.TemplateResponse("auction/auction_results.html", ctx)


# =========================
# AJAX APIs
# =========================
@router.get("/auction/results/api/projects/{project_id}/lots")
async def api_list_lots(
    request: Request,
    project_id: int = Path(..., ge=1),
    q: Optional[str] = Query(None),
    result_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=500),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    params: Dict[str, Any] = {"page": page, "size": size}
    if q:
        params["q"] = q
    if result_status:
        params["result_status"] = result_status

    st, js = await _get_json(f"/api/v1/auction-results/projects/{project_id}/lots", token, params)
    return JSONResponse(js, status_code=200 if st == 200 else 502)


@router.get("/auction/results/api/projects/{project_id}/lots/{lot_code}/eligible-customers")
async def api_eligible_customers(
    request: Request,
    project_id: int = Path(..., ge=1),
    lot_code: str = Path(..., min_length=1),
    include_unpaid: bool = Query(False),
    q: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    params: Dict[str, Any] = {"limit": limit, "include_unpaid": include_unpaid}
    if q:
        params["q"] = q

    st, js = await _get_json(
        f"/api/v1/auction-results/projects/{project_id}/lots/{lot_code}/eligible-customers",
        token,
        params,
    )
    return JSONResponse(js, status_code=200 if st == 200 else 502)


@router.put("/auction/results/api/projects/{project_id}/lots/{lot_code}")
async def api_save_one(
    request: Request,
    project_id: int = Path(..., ge=1),
    lot_code: str = Path(..., min_length=1),
    payload: Dict[str, Any] = Body(...),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _put_json(f"/api/v1/auction-results/projects/{project_id}/lots/{lot_code}", token, payload)
    return JSONResponse(js, status_code=200 if st == 200 else 502)


@router.post("/auction/results/api/projects/{project_id}/bulk-upsert")
async def api_bulk_save(
    request: Request,
    project_id: int = Path(..., ge=1),
    payload: Dict[str, Any] = Body(...),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    st, js = await _post_json(f"/api/v1/auction-results/projects/{project_id}/bulk-upsert", token, payload)
    return JSONResponse(js, status_code=200 if st == 200 else 502)


# (Optional) nếu sau bạn muốn list "lô đủ điều kiện" riêng
@router.get("/auction/results/api/projects/{project_id}/eligible-lots")
async def api_eligible_lots(
    request: Request,
    project_id: int = Path(..., ge=1),
    q: Optional[str] = Query(None),
    include_unpaid: bool = Query(False),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=500),
):
    token = get_access_token(request)
    if not token:
        return _unauth_json()

    params: Dict[str, Any] = {"page": page, "size": size, "include_unpaid": include_unpaid}
    if q:
        params["q"] = q

    st, js = await _get_json(f"/api/v1/auction-results/projects/{project_id}/eligible-lots", token, params)
    return JSONResponse(js, status_code=200 if st == 200 else 502)
