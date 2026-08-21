# routers/profit.py — Module Lợi nhuận (tách biệt khỏi Báo cáo dự án)
from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.auth import get_access_token
from utils.templates import templates

router = APIRouter(tags=["profit"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


def _unauth() -> JSONResponse:
    return JSONResponse({"error": "unauthorized"}, status_code=401)


async def _get_json(path: str, token: str, params: Dict[str, Any] | None = None) -> tuple[int, Any]:
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.get(url, headers=headers, params=params or {})
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"detail": (r.text or "")[:500]}


async def _post_json(path: str, token: str, payload: Dict[str, Any] | None = None) -> tuple[int, Any]:
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.post(url, headers=headers, json=payload or {})
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"detail": (r.text or "")[:500]}


async def _patch_json(path: str, token: str, payload: Dict[str, Any]) -> tuple[int, Any]:
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.patch(url, headers=headers, json=payload)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"detail": (r.text or "")[:500]}


async def _load_projects(token: str, project_param: Optional[str]) -> tuple[list[dict], str]:
    st, pj = await _get_json("/api/v1/projects", token, {"size": 1000})
    projects: list[dict] = []
    selected = (project_param or "").strip().upper()
    if st == 200 and isinstance(pj, dict):
        projects = pj.get("data") or pj.get("items") or []
        if not selected and len(projects) == 1:
            selected = (projects[0].get("project_code") or "").upper()
    return projects, selected


def _project_id_from_code(projects: list[dict], project_code: str) -> int | None:
    code = (project_code or "").strip().upper()
    for p in projects or []:
        if (p.get("project_code") or "").strip().upper() == code:
            pid = p.get("id") or p.get("project_id")
            return int(pid) if pid is not None else None
    return None


@router.get("/profit", response_class=HTMLResponse)
async def profit_dashboard_page(
    request: Request,
    from_month: Optional[str] = Query(None, description="YYYY-MM"),
    to_month: Optional[str] = Query(None, description="YYYY-MM"),
    status: str = Query("ALL"),
    search: str = Query(""),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fprofit", status_code=303)

    params: Dict[str, Any] = {"status": status, "search": search}
    if from_month:
        params["from_month"] = from_month
    if to_month:
        params["to_month"] = to_month

    report = None
    error = None
    st, js = await _get_json("/api/v1/reports/auction-revenue", token, params)
    if st == 200:
        report = js
    else:
        error = {"status": st, "body": js}

    return templates.TemplateResponse(
        "profit/dashboard.html",
        {
            "request": request,
            "title": "Lợi nhuận",
            "report": report,
            "from_month": (report or {}).get("period", {}).get("from") or from_month,
            "to_month": (report or {}).get("period", {}).get("to") or to_month,
            "status_filter": status,
            "search": search,
            "error": error,
        },
    )


@router.get("/profit/project", response_class=HTMLResponse)
async def profit_project_detail_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_code"),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=%2Fprofit%2Fproject", status_code=303)

    projects, selected_project = await _load_projects(token, project)
    project_id = _project_id_from_code(projects, selected_project) if selected_project else None

    summary = None
    error = None
    if project_id:
        st, js = await _get_json(f"/api/v1/projects/{project_id}/revenue-summary", token, {})
        if st == 200:
            summary = js
        else:
            error = {"status": st, "body": js}

    return templates.TemplateResponse(
        "profit/project_detail.html",
        {
            "request": request,
            "title": "Chi tiết lợi nhuận dự án",
            "projects": projects,
            "project": selected_project,
            "project_id": project_id,
            "summary": summary,
            "error": error,
        },
    )


@router.post("/profit/project/recalculate", response_class=JSONResponse)
async def profit_project_recalculate_proxy(request: Request):
    token = get_access_token(request)
    if not token:
        return _unauth()
    try:
        body = await request.json()
    except Exception:
        body = {}
    project_id = body.get("project_id")
    if not project_id:
        return JSONResponse({"error": "project_id required"}, status_code=400)
    st, js = await _post_json(
        f"/api/v1/projects/{int(project_id)}/revenue/recalculate",
        token,
        {k: v for k, v in body.items() if k != "project_id"},
    )
    return JSONResponse(js, status_code=st)


@router.patch("/profit/project/config", response_class=JSONResponse)
async def profit_project_config_proxy(request: Request):
    token = get_access_token(request)
    if not token:
        return _unauth()
    try:
        body = await request.json()
    except Exception:
        body = {}
    project_id = body.get("project_id")
    if not project_id:
        return JSONResponse({"error": "project_id required"}, status_code=400)
    payload = {k: v for k, v in body.items() if k != "project_id"}
    st, js = await _patch_json(
        f"/api/v1/projects/{int(project_id)}/revenue/config",
        token,
        payload,
    )
    return JSONResponse(js, status_code=st)
