from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction_refunds"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# ---------- logging helper ----------
def _log(msg: str):
    print(f"[REFUNDS_B] {msg}")


def _preview_body(data: Any, limit: int = 350) -> str:
    try:
        import json
        s = json.dumps(data, ensure_ascii=False)
    except Exception:
        s = str(data)
    return s[:limit] + ("...(truncated)" if len(s) > limit else "")


class ServiceAError(Exception):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        super().__init__(f"ServiceAError status={status}")


async def _get_json(path: str, token: str, params: Dict[str, Any] | None = None) -> Any:
    url = SERVICE_A_BASE_URL.rstrip("/") + path
    _log(f"GET {url} params={params}")
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
    try:
        js = r.json()
    except Exception:
        js = {"raw": r.text}
    if r.status_code >= 400:
        _log(f"ERR {r.status_code} body={_preview_body(js)}")
        raise ServiceAError(r.status_code, js)
    return js


async def _post_json(path: str, token: str, params: Dict[str, Any] | None = None) -> Any:
    url = SERVICE_A_BASE_URL.rstrip("/") + path
    _log(f"POST {url} params={params}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
    try:
        js = r.json()
    except Exception:
        js = {"raw": r.text}
    if r.status_code >= 400:
        _log(f"ERR {r.status_code} body={_preview_body(js)}")
        raise ServiceAError(r.status_code, js)
    return js


def _parse_projects(js: Any) -> List[Dict[str, Any]]:
    """
    Tolerate multiple response shapes:
    - list
    - {"items":[...]}
    - {"data":[...]}
    - {"data":{"items":[...]}}
    - {"projects":[...]}
    """
    if isinstance(js, list):
        return js
    if not isinstance(js, dict):
        return []
    if isinstance(js.get("items"), list):
        return js.get("items") or []
    if isinstance(js.get("data"), list):
        return js.get("data") or []
    if isinstance(js.get("data"), dict) and isinstance(js["data"].get("items"), list):
        return js["data"].get("items") or []
    if isinstance(js.get("projects"), list):
        return js.get("projects") or []
    return []


@router.get("/auction/refunds", response_class=HTMLResponse)
async def refunds_page(
    request: Request,
    project: str = Query("", alias="project"),
    q: str = Query(""),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=2000),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/public/login", status_code=302)

    error = None
    projects = []
    data = None
    project_id = None

    # --- Load projects (like 5.3): try authenticated, then public
    try:
        candidates = [
            ("/api/v1/projects", {"page": 1, "size": 2000}),
            ("/api/v1/projects/public", {"page": 1, "size": 2000}),
            ("/api/v1/projects/public", {}),
        ]
        js = None
        last_err = None
        for path, params in candidates:
            try:
                js = await _get_json(path, token, params=params)
                if js is not None:
                    break
            except ServiceAError as e:
                last_err = e
                js = None
        if js is None and last_err:
            raise last_err

        projects = _parse_projects(js)

    except ServiceAError as e:
        error = {"status": e.status, "body": e.body}
        projects = []

    # Map project_code -> project_id
    if project and projects:
        for p in projects:
            code = p.get("project_code") or p.get("code") or ""
            if str(code) == str(project):
                project_id = p.get("id")
                break

    # Load refund candidates only if project selected (like 5.3 behavior)
    if project_id:
        try:
            params = {
                "project_id": int(project_id),
                "q": q or "",
                "page": page,
                "size": size,
            }
            data = await _get_json("/api/v1/auction/refunds", token, params=params)
        except ServiceAError as e:
            error = {"status": e.status, "body": e.body}
            data = None

    return templates.TemplateResponse(
        "auction/auction_refunds.html",
        {
            "request": request,
            "projects": projects,
            "project": project,
            "project_id": project_id,
            "q": q,
            "page": page,
            "size": size,
            "data": data,
            "error": error,
        },
    )


@router.post("/auction/refunds/rebuild")
async def refunds_rebuild(request: Request):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/public/login", status_code=302)

    # rebuild for selected project if provided
    form = await request.form()
    project_id = (form.get("project_id") or "").strip()

    try:
        params = {"project_id": int(project_id)} if project_id else None
        await _post_json("/api/v1/auction/refunds/rebuild", token, params=params)
    except ServiceAError as e:
        return JSONResponse({"ok": False, "status": e.status, "body": e.body}, status_code=500)

    return RedirectResponse(
        url=f"/auction/refunds?project_id={project_id}" if project_id else "/auction/refunds",
        status_code=303,
    )
