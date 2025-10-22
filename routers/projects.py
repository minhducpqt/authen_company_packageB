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

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

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
    lots_page = {"data": [], "total": 0}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            # 1) Lấy project
            st, data = await _get_json(
                client, EP_DETAIL.format(project_id=project_id), {"Authorization": f"Bearer {token}"}
            )
            if st == 200 and isinstance(data, dict):
                project = data
            else:
                load_err = f"Không tải được dự án (HTTP {st})."

            # 2) Nếu có project_code thì lấy danh sách lô theo project_code
            if project and project.get("project_code"):
                params = {"project_code": project["project_code"], "size": 1000}
                lst_st, lst = await _get_json(
                    client, f"/api/v1/lots?{urlencode(params)}", {"Authorization": f"Bearer {token}"}
                )
                if lst_st == 200 and isinstance(lst, dict):
                    lots_page = {
                        "data": lst.get("data", []),
                        "total": lst.get("total", 0),
                    }
                else:
                    # không chặn trang — chỉ ghi nhận lỗi phần lots
                    if not load_err:
                        load_err = f"Không tải được danh sách lô (HTTP {lst_st})."

    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/projects/detail.html",
        {
            "request": request,
            "title": f"Dự án {project.get('project_code') if project else f'#{project_id}'}",
            "me": me,
            "project": project,
            "lots_page": lots_page,
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

# =========================
# X) DATA CHO DROPDOWN DỰ ÁN (ACTIVE, theo scope công ty)
# =========================
from fastapi.responses import JSONResponse
import base64, json as pyjson

EP_PUBLIC_PROJECTS = "/api/v1/projects/public"
EP_COMPANY_PROFILE = "/api/v1/company/profile"

def _b64url_decode(data: str) -> bytes:
    # helper đọc payload JWT (không verify)
    data += "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data.encode("utf-8"))

def _company_from_jwt(token: str | None) -> str | None:
    if not token or token.count(".") != 2:
        return None
    try:
        payload_b = _b64url_decode(token.split(".")[1])
        payload = pyjson.loads(payload_b.decode("utf-8"))
        cc = payload.get("company_code") or payload.get("companyCode")
        return (cc or "").strip() or None
    except Exception:
        return None

@router.get("/data", response_class=JSONResponse)
async def projects_data(
    request: Request,
    status: Optional[str] = Query("ACTIVE", description="ACTIVE|INACTIVE"),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(1000, ge=1, le=1000),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # 1) me.company_code
    me = await fetch_me(token)
    company_code: Optional[str] = (me or {}).get("company_code")

    # 2) /api/v1/company/profile (nếu cần)
    if not company_code:
        try:
            async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
                r_prof = await client.get(EP_COMPANY_PROFILE, headers={"Authorization": f"Bearer {token}"})
            if r_prof.status_code == 200:
                prof = r_prof.json() or {}
                # thử vài key phổ biến
                company_code = (
                    prof.get("company_code")
                    or (prof.get("company") or {}).get("company_code")
                    or (prof.get("profile") or {}).get("company_code")
                )
        except Exception:
            pass

    # 3) Fallback: đọc từ JWT claim
    if not company_code:
        company_code = _company_from_jwt(token)

    if not company_code:
        return JSONResponse(
            {"error": "missing_company_code", "message": "Không xác định được công ty từ token/scope."},
            status_code=400,
        )

    # 4) Gọi danh sách dự án PUBLIC theo company_code
    params = [("company_code", company_code), ("page", page), ("size", size)]
    if status:
        params.append(("status", status))
    if q:
        params.append(("q", q))

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.get(EP_PUBLIC_PROJECTS, params=params, headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
            # trả lỗi kèm chi tiết để dễ debug curl
            detail = None
            try:
                detail = r.json()
            except Exception:
                detail = (r.text or "")[:500]
            return JSONResponse(
                {"error": "projects_fetch_failed", "status": r.status_code, "detail": detail},
                status_code=502,
            )

        raw = r.json() or {}
        items = raw.get("data") or []
        def pick(x: dict) -> dict:
            code = x.get("project_code") or x.get("code")
            name = x.get("name") or code
            return {"project_code": code, "name": name, "status": x.get("status")}
        data = [pick(x) for x in items if x]

        return JSONResponse(
            {"data": data, "page": raw.get("page", page), "size": raw.get("size", size), "total": raw.get("total", len(data))},
            status_code=200,
        )
    except Exception as e:
        return JSONResponse({"error": "exception", "message": str(e)}, status_code=500)

# --- THÊM VÀO CUỐI FILE routers/projects.py (hoặc ngay dưới phần LIST) ---
from fastapi.responses import JSONResponse

@router.get("/options/active", response_class=JSONResponse)
async def project_options_active(
    request: Request,
    q: Optional[str] = Query(None, description="search by code/name (optional)"),
    size: int = Query(1000, ge=1, le=1000),
):
    """
    Trả danh sách dự án ACTIVE của công ty (dùng làm dropdown).
    - Lấy company_code từ /auth/me
    - Gọi Service A: GET /api/v1/projects/public?company_code=...&status=ACTIVE
    - Chuẩn hóa kết quả: {data: [{project_code, name}, ...]}
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    company_code = (me or {}).get("company_code")
    if not company_code:
        return JSONResponse({"error": "no_company_code"}, status_code=400)

    params = {
        "company_code": company_code,
        "status": "ACTIVE",
        "page": 1,
        "size": size,
    }
    if q:
        params["q"] = q

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.get("/api/v1/projects/public", params=params,
                                 headers={"Authorization": f"Bearer {token}"})
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "msg": str(e)}, status_code=502)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "upstream_5xx", "msg": r.text[:300]}, status_code=502)
    if r.status_code != 200:
        return JSONResponse({"error": "upstream", "status": r.status_code}, status_code=502)

    js = r.json() or {}
    items = js.get("data") or js.get("items") or js  # phòng khi service A trả mảng thẳng
    if not isinstance(items, list):
        items = []

    # Chuẩn hóa trường cho dropdown
    data = []
    for p in items:
        code = (p or {}).get("project_code") or (p or {}).get("code")
        name = (p or {}).get("name") or code
        if code:
            data.append({"project_code": code, "name": name})

    return JSONResponse({"data": data}, status_code=200)
