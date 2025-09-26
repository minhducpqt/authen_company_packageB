# routers/projects.py
from __future__ import annotations

import os
import httpx
from typing import Optional
from urllib.parse import urlencode, quote

from fastapi import APIRouter, Request, Form, Query, Path, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me

router = APIRouter(prefix="/projects", tags=["projects"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")

# ---- Endpoints của Service A (đặt 1 chỗ để dễ đổi) ----
EP_LIST         = "/api/v1/projects"
EP_CREATE       = "/api/v1/projects"
EP_DETAIL       = "/api/v1/projects/{project_id}"
EP_ENABLE       = "/api/v1/projects/{project_id}/enable"
EP_DISABLE      = "/api/v1/projects/{project_id}/disable"
EP_TPL_XLSX     = "/api/v1/projects/template"
EP_EXPORT_XLSX  = "/api/v1/projects/export_xlsx"
EP_IMPORT_XLSX  = "/api/v1/projects/import_xlsx"
# -------------------------------------------------------

# ========== helpers ==========
async def _get_json(client: httpx.AsyncClient, url: str, headers: dict):
    r = await client.get(url, headers=headers)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None

async def _post_json(client: httpx.AsyncClient, url: str, headers: dict, payload: dict | None):
    r = await client.post(url, headers=headers, json=payload or {})
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None
# =============================

# =========================
# LIST
# =========================
@router.get("", response_class=HTMLResponse)
async def list_projects(
    request: Request,
    q: Optional[str] = Query(None, description="free text by name/code"),
    status: Optional[str] = Query("ACTIVE", description="ACTIVE|INACTIVE|ALL"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote('/projects')}", status_code=303)

    params = {"page": page, "size": size}
    if q:
        params["q"] = q
    if status and status != "ALL":
        params["status"] = status

    load_err = None
    page_data = {"data": [], "page": page, "size": size, "total": 0}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            st, data = await _get_json(
                client, f"{EP_LIST}?{urlencode(params)}", {"Authorization": f"Bearer {token}"}
            )
            if st == 200 and isinstance(data, dict):
                page_data = {
                    "data": data.get("data", []),
                    "page": data.get("page", page),
                    "size": data.get("size", size),
                    "total": data.get("total", 0),
                }
            else:
                load_err = f"Không tải được danh sách dự án (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/projects/list.html",
        {
            "request": request,
            "title": "Quản lý dự án",
            "me": me,
            "filters": {"q": q or "", "status": status or "ALL"},
            "page": page_data,
            "load_err": load_err,
        },
    )

# =========================
# DETAIL
# =========================
@router.get("/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: int = Path(...)):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url=f"/login?next={quote(f'/projects/{project_id}')}", status_code=303)

    load_err = None
    project = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            st, data = await _get_json(
                client, EP_DETAIL.format(project_id=project_id), {"Authorization": f"Bearer {token}"}
            )
            if st == 200 and isinstance(data, dict):
                project = data
            else:
                load_err = f"Không tải được dự án (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/projects/detail.html",
        {
            "request": request,
            "title": f"Dự án #{project_id}",
            "me": me,
            "project": project,
            "load_err": load_err,
        },
    )

# =========================
# CREATE - FORM
# =========================
@router.get("/create", response_class=HTMLResponse)
async def create_form(request: Request):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/projects/create", status_code=303)
    return templates.TemplateResponse(
        "pages/projects/create.html",
        {"request": request, "title": "Thêm dự án", "me": me},
    )

# =========================
# CREATE - ACTION
# =========================
@router.post("/create")
async def create_submit(
    request: Request,
    project_code: str = Form(...),
    name: str = Form(...),
    description: str = Form(""),
    location: str = Form(""),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=/projects/create", status_code=303)

    payload = {
        "project_code": project_code.strip(),
        "name": name.strip(),
        "description": description.strip() or None,
        "location": location.strip() or None,
    }

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
        st, _ = await _post_json(client, EP_CREATE, {"Authorization": f"Bearer {token}"}, payload)

    to = "/projects?msg=created" if st == 200 else "/projects?err=create_failed"
    return RedirectResponse(url=to, status_code=303)

# =========================
# TOGGLE (Admin)
# =========================
@router.post("/{project_id}/toggle")
async def toggle_project(
    request: Request,
    project_id: int = Path(...),
    action: str = Form(...),  # enable|disable
    next: Optional[str] = Form(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url=f"/login?next=/projects/{project_id}", status_code=303)

    action = (action or "").lower()
    ep = EP_ENABLE if action == "enable" else EP_DISABLE if action == "disable" else None
    if not ep:
        redir = next or "/projects"
        return RedirectResponse(url=f"{redir}?err=bad_action", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
        st, _ = await _post_json(
            client, ep.format(project_id=project_id), {"Authorization": f"Bearer {token}"}, None
        )

    redir = next or "/projects"
    to = f"{redir}?msg=toggled" if st == 200 else f"{redir}?err=toggle_failed"
    return RedirectResponse(url=to, status_code=303)

# =========================
# IMPORT/EXPORT
# =========================
@router.get("/import", response_class=HTMLResponse)
async def import_form(request: Request):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/projects/import", status_code=303)
    return templates.TemplateResponse(
        "pages/projects/import.html",
        {"request": request, "title": "Nhập dự án từ Excel", "me": me},
    )

@router.get("/template")
async def download_template(request: Request):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=/projects/template", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
        r = await client.get(EP_TPL_XLSX, headers={"Authorization": f"Bearer {token}"})
    return StreamingResponse(
        iter([r.content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="projects_template.xlsx"'},
    )

@router.get("/export")
async def export_xlsx(request: Request, q: str | None = None, status: str | None = "ACTIVE"):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=/projects/export", status_code=303)

    params = {}
    if q:
        params["q"] = q
    if status and status != "ALL":
        params["status"] = status

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=40.0) as client:
        r = await client.get(EP_EXPORT_XLSX, params=params, headers={"Authorization": f"Bearer {token}"})
    return StreamingResponse(
        iter([r.content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="projects_export.xlsx"'},
    )

@router.post("/import")
async def import_xlsx(request: Request, file: UploadFile = File(...)):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/login?next=/projects/import", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=180.0) as client:
        files = {"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")}
        r = await client.post(EP_IMPORT_XLSX, headers={"Authorization": f"Bearer {token}"}, files=files)

    to = "/projects?msg=import_ok" if r.status_code == 200 else "/projects/import?err=import_failed"
    return RedirectResponse(url=to, status_code=303)
