# routers/projects.py
from __future__ import annotations

import os
import json
from typing import Optional
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, Request, Form, Query, Path, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from utils.templates import templates
from utils.auth import get_access_token, fetch_me
from utils.excel_templates import build_projects_lots_template
from utils.excel_import import handle_import_preview  # chỉ dùng preview

router = APIRouter(prefix="/projects", tags=["projects"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")

# Endpoints Service A
EP_LIST            = "/api/v1/projects"
EP_CREATE_PROJ     = "/api/v1/projects"
EP_DETAIL          = "/api/v1/projects/{project_id}"
EP_ENABLE          = "/api/v1/projects/{project_id}/enable"
EP_DISABLE         = "/api/v1/projects/{project_id}/disable"
EP_BYCODE_PROJ     = "/api/v1/projects/by_code/{code}"
EP_UPDATE_PROJ     = "/api/v1/projects/{pid}"
EP_EXPORT_XLSX     = "/api/v1/projects/export_xlsx"
EP_IMPORT_XLSX     = "/api/v1/projects/import_xlsx"   # (nếu dùng Service A build)
EP_CREATE_LOT      = "/api/v1/lots"

# helpers http
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


# =====================================================================
# 1) TEMPLATE / EXPORT / IMPORT  --> đặt trước /{project_id}
# =====================================================================

@router.get("/template")
async def download_template(request: Request):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/projects/template", status_code=303)

    company_code = me.get("company_code")
    if not company_code:
        return RedirectResponse(url="/projects?err=no_company_code", status_code=303)

    # Build template tại WEB (không gọi Service A)
    return await build_projects_lots_template(token, company_code)


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


@router.post("/import/preview", response_class=HTMLResponse)
async def import_preview(request: Request, file: UploadFile = File(...)):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/projects/import", status_code=303)

    file_bytes = await file.read()
    preview = await handle_import_preview(file_bytes, token)

    if not preview.get("ok"):
        # Lỗi template / dữ liệu → quay về form và báo lỗi
        return templates.TemplateResponse(
            "pages/projects/import.html",
            {"request": request, "title": "Nhập dự án từ Excel", "me": me, "err": preview.get("errors")},
            status_code=400,
        )

    company_code = (me or {}).get("company_code") or ""
    return templates.TemplateResponse(
        "pages/projects/import_preview.html",
        {
            "request": request,
            "title": "Xem trước import dự án",
            "me": me,
            "company_code": company_code,
            "payload_json": json.dumps(preview, ensure_ascii=False),
            "preview": preview,
        },
    )


@router.post("/import/apply", response_class=HTMLResponse)
async def import_apply(
    request: Request,
    payload: str = Form(...),
    company_code: str = Form(...),
    force_replace: bool = Form(False),
):
    """
    Ghi từng dự án + lô:
    - Project: POST; nếu 409 và force_replace=True → GET by_code lấy id rồi PUT (giữ status='INACTIVE').
    - Lot: POST; nếu 409 hiện bỏ qua (chưa ghi đè).
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/projects/import", status_code=303)

    try:
        data = json.loads(payload)
    except Exception:
        return templates.TemplateResponse(
            "pages/projects/import.html",
            {"request": request, "title": "Nhập dự án từ Excel", "me": me, "err": "Payload không hợp lệ."},
            status_code=400,
        )

    projects = data.get("projects") or []
    lots     = data.get("lots") or []
    errors: list[str] = []
    created_codes: list[str] = []
    replaced_codes: list[str] = []

    headers = {"Authorization": f"Bearer {token}", "X-Company-Code": company_code}

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
        # --- Ghi PROJECTS ---
        for p in projects:
            code = (p.get("project_code") or "").strip()
            name = (p.get("name") or "").strip()
            body = {
                "project_code": code,
                "name": name,
                "description": p.get("description") or None,
                "location": p.get("location") or None,
                "status": "INACTIVE",
            }
            # Tạo
            r = await client.post(EP_CREATE_PROJ, json=body, headers=headers)
            if r.status_code == 200:
                created_codes.append(code)
            elif r.status_code == 409:
                if force_replace:
                    # Lấy id theo code rồi PUT
                    r0 = await client.get(EP_BYCODE_PROJ.format(code=code), headers=headers,
                                          params={"company_code": company_code})
                    if r0.status_code != 200:
                        errors.append(f"Dự án {code}: không tìm được id để ghi đè (HTTP {r0.status_code}).")
                        continue
                    pid = (r0.json() or {}).get("id")
                    if not isinstance(pid, int):
                        errors.append(f"Dự án {code}: id không hợp lệ khi ghi đè.")
                        continue
                    r1 = await client.put(EP_UPDATE_PROJ.format(pid=pid), json=body, headers=headers)
                    if r1.status_code == 200:
                        replaced_codes.append(code)
                    else:
                        errors.append(f"Dự án {code}: ghi đè thất bại (HTTP {r1.status_code}).")
                else:
                    errors.append(f"Dự án {code}: đã tồn tại, bật 'Ghi đè' để cập nhật.")
            else:
                try:
                    msg = (r.json() or {}).get("detail") or (r.json() or {}).get("message") or ""
                except Exception:
                    msg = ""
                errors.append(f"Dự án {code}: tạo thất bại (HTTP {r.status_code}) {msg}")

            # --- Ghi LOTS cho project này ---
            proj_lots = [l for l in lots if (l.get("project_code") or "").strip().upper() == code.upper()]
            for l in proj_lots:
                lot_body = {
                    "company_code": company_code,
                    "project_code": code,
                    "lot_code": l.get("lot_code"),
                    "name": l.get("name") or None,
                    "description": l.get("description") or None,
                    "starting_price": l.get("starting_price"),
                    "deposit_amount": l.get("deposit_amount"),
                    "area": l.get("area"),
                    "status": "AVAILABLE",
                }
                rl = await client.post(EP_CREATE_LOT, json=lot_body, headers=headers)
                if rl.status_code in (200, 201, 204):
                    continue
                if rl.status_code == 409:
                    # Chưa có API update-by-code cho lot → BỎ QUA (không ghi đè)
                    continue
                try:
                    lmsg = (rl.json() or {}).get("detail") or (rl.json() or {}).get("message") or ""
                except Exception:
                    lmsg = ""
                errors.append(
                    f"Lô {l.get('lot_code')} thuộc {code}: tạo thất bại (HTTP {rl.status_code}) {lmsg}"
                )

    # Kết luận
    if errors and (created_codes or replaced_codes):
        # Partial OK
        return RedirectResponse(
            url=f"/projects?msg=import_ok&c={len(created_codes)}&r={len(replaced_codes)}",
            status_code=303,
        )
    if not errors:
        return RedirectResponse(
            url=f"/projects?msg=import_ok&c={len(created_codes)}&r={len(replaced_codes)}",
            status_code=303,
        )

    # Có lỗi → quay lại preview hiển thị lỗi
    return templates.TemplateResponse(
        "pages/projects/import_preview.html",
        {
            "request": request,
            "title": "Xem trước import dự án",
            "me": me,
            "company_code": company_code,
            "payload_json": payload,           # giữ để người dùng Apply lại nếu muốn
            "preview": json.loads(payload),
            "err": errors,
        },
        status_code=207 if (created_codes or replaced_codes) else 400,
    )


# =========================
# 2) LIST
# =========================
@router.get("", response_class=HTMLResponse)
async def list_projects(
    request: Request,
    q: Optional[str] = Query(None, description="free text by name/code"),
    status: Optional[str] = Query("ALL", description="ACTIVE|INACTIVE|ALL"),
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
# 3) DETAIL (đặt SAU route tĩnh)
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
# 4) CREATE (form + submit)
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
        "project_code": (project_code or "").strip(),
        "name": (name or "").strip(),
        "description": (description or "").strip() or None,
        "location": (location or "").strip() or None,
    }

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
        st, _ = await _post_json(client, EP_CREATE_PROJ, {"Authorization": f"Bearer {token}"}, payload)

    to = "/projects?msg=created" if st == 200 else "/projects?err=create_failed"
    return RedirectResponse(url=to, status_code=303)


# =========================
# 5) TOGGLE (Admin)
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
