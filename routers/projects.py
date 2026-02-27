# routers/projects.py (Service B) - FINAL (lots đã tách sang routers/lots.py)
from __future__ import annotations

import os
import json
import base64
from typing import Optional
from urllib.parse import urlencode, quote

import httpx
from fastapi import (
    APIRouter,
    Request,
    Form,
    Query,
    Path,
    UploadFile,
    File,
    HTTPException,
)
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
    JSONResponse,
)

from utils.templates import templates
from utils.auth import get_access_token, fetch_me
from utils.excel_templates import build_projects_lots_template
from utils.excel_import import handle_import_preview  # chỉ dùng preview

import json as pyjson  # cho decode JWT payload

# ✅ import helper lots từ routers/lots.py (Service B)
from routers.lots import sa_create_lot, sa_list_lots_by_project_code

router = APIRouter(prefix="/projects", tags=["projects"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

# Endpoints Service A (projects.py)
EP_LIST              = "/api/v1/projects"
EP_CREATE_PROJ       = "/api/v1/projects"
EP_DETAIL            = "/api/v1/projects/{project_id}"
EP_ENABLE            = "/api/v1/projects/{project_id}/enable"
EP_DISABLE           = "/api/v1/projects/{project_id}/disable"
EP_BYCODE_PROJ       = "/api/v1/projects/by_code/{code}"
EP_UPDATE_PROJ       = "/api/v1/projects/{pid}"
EP_EXPORT_XLSX       = "/api/v1/projects/export_xlsx"
EP_IMPORT_XLSX       = "/api/v1/projects/import_xlsx"   # (nếu dùng Service A build)
EP_DEADLINES         = "/api/v1/projects/{project_id}/deadlines"
EP_PUBLIC_PROJECTS   = "/api/v1/projects/public"
EP_COMPANY_PROFILE   = "/api/v1/company/profile"
EP_AUCTION_MODE      = "/api/v1/projects/{project_id}/auction_mode"  # <-- NEW
EP_AUCTION_CONFIG    = "/api/v1/projects/{project_id}/auction_config"   # <-- NEW
EP_BID_TICKET_CONFIG = "/api/v1/projects/{project_id}/bid_ticket_config"  # <-- NEW


# ==============================
# helpers http
# ==============================
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

def _safe_str(x) -> str:
    try:
        return str(x)
    except Exception:
        return ""


def _pack_toggle_error(status_code: int, data: dict | None) -> tuple[str, str, str]:
    """
    Return (err_msg, err_hint, err_fields)
    - err_fields: dạng "- ...\n- ..."
    """
    err_msg = "Không thể thay đổi trạng thái dự án."
    err_hint = ""
    err_fields = ""

    detail = None
    if isinstance(data, dict):
        detail = data.get("detail", data)

    # detail string
    if isinstance(detail, str) and detail.strip():
        err_msg = detail.strip()
        # gợi ý riêng cho 423
        if status_code == 423:
            err_hint = "Tài khoản công ty đang bị khóa do công nợ/chi phí. Vui lòng kiểm tra Billing hoặc liên hệ nhà cung cấp."
        return err_msg, err_hint, err_fields

    # detail dict
    if isinstance(detail, dict):
        if detail.get("msg"):
            err_msg = _safe_str(detail.get("msg"))
        if detail.get("hint"):
            err_hint = _safe_str(detail.get("hint"))

        errs = detail.get("errors")
        if isinstance(errs, list):
            lines = []
            for e in errs:
                if isinstance(e, dict):
                    m = (e.get("message") or e.get("msg") or "").strip()
                    f = (e.get("field") or "").strip()
                    if m and f:
                        lines.append(f"- {m} ({f})")
                    elif m:
                        lines.append(f"- {m}")
            if lines:
                err_fields = "\n".join(lines)

    # fallback cho 423 nếu chưa có hint
    if status_code == 423 and not err_hint:
        err_hint = "Tài khoản công ty đang bị khóa do công nợ/chi phí. Vui lòng kiểm tra Billing hoặc liên hệ nhà cung cấp."

    return err_msg, err_hint, err_fields

def _b64url_decode(data: str) -> bytes:
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


def _auth_headers(request: Request) -> dict:
    # Nếu bạn xác thực bằng cookie/bearer, bê nguyên header Authorization sang Service A
    h: dict[str, str] = {}
    auth = request.headers.get("Authorization")
    if auth:
        h["Authorization"] = auth
    return h


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

    params: dict[str, str] = {}
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
):
    """
    Ghi từng dự án + lô:
    - Project: POST; nếu đã tồn tại (409) → BÁO LỖI, KHÔNG GHI ĐÈ.
    - Lot: POST; nếu 409 → bỏ qua (không ghi đè).
    """
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/projects/import", status_code=303)

    # ⛔ Chặn cứng nếu FE cũ vẫn gửi force_replace
    try:
        form = await request.form()
        if form.get("force_replace"):
            return templates.TemplateResponse(
                "pages/projects/import_preview.html",
                {
                    "request": request,
                    "title": "Xem trước import dự án",
                    "me": me,
                    "company_code": company_code,
                    "payload_json": payload,
                    "preview": json.loads(payload),
                    "err": "Tính năng ghi đè dự án đã bị vô hiệu hoá.",
                },
                status_code=400,
            )
    except Exception:
        pass

    try:
        data = json.loads(payload)
    except Exception:
        return templates.TemplateResponse(
            "pages/projects/import.html",
            {
                "request": request,
                "title": "Nhập dự án từ Excel",
                "me": me,
                "err": "Payload không hợp lệ.",
            },
            status_code=400,
        )

    projects = data.get("projects") or []
    lots     = data.get("lots") or []

    errors: list[str] = []
    created_codes: list[str] = []

    headers = {"Authorization": f"Bearer {token}", "X-Company-Code": company_code}

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
        # -----------------------
        # 1) PROJECTS
        # -----------------------
        for p in projects:
            code = (p.get("project_code") or "").strip()
            name = (p.get("name") or "").strip()

            if not code or not name:
                errors.append("Thiếu project_code hoặc name.")
                continue

            body = {
                "project_code": code,
                "name": name,
                "description": p.get("description") or None,
                "location": p.get("location") or None,
                "status": "INACTIVE",
            }

            r = await client.post(EP_CREATE_PROJ, json=body, headers=headers)

            if r.status_code == 200:
                created_codes.append(code)

            elif r.status_code == 409:
                # ❌ KHÔNG GHI ĐÈ
                errors.append(f"Dự án {code}: đã tồn tại, không cho phép ghi đè.")

            else:
                try:
                    msg = (r.json() or {}).get("detail") or (r.json() or {}).get("message") or ""
                except Exception:
                    msg = ""
                errors.append(f"Dự án {code}: tạo thất bại (HTTP {r.status_code}) {msg}")

            # -----------------------
            # 2) LOTS (theo project_code)
            # -----------------------
            proj_lots = [
                l for l in lots
                if (l.get("project_code") or "").strip().upper() == code.upper()
            ]

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
                    "bid_step_vnd": l.get("bid_step_vnd"),
                    "status": "AVAILABLE",
                }

                rl_st, rl_js = await sa_create_lot(
                    client,
                    headers=headers,
                    lot_body=lot_body,
                )

                if rl_st in (200, 201, 204):
                    continue

                if rl_st == 409:
                    # ❌ không ghi đè lot
                    continue

                try:
                    lmsg = (rl_js or {}).get("detail") or (rl_js or {}).get("message") or ""
                except Exception:
                    lmsg = ""

                errors.append(
                    f"Lô {l.get('lot_code')} thuộc {code}: tạo thất bại (HTTP {rl_st}) {lmsg}"
                )

    # -----------------------
    # KẾT LUẬN
    # -----------------------
    if not errors:
        return RedirectResponse(
            url=f"/projects?msg=import_ok&c={len(created_codes)}",
            status_code=303,
        )

    if created_codes:
        # Partial OK
        return RedirectResponse(
            url=f"/projects?msg=import_ok&c={len(created_codes)}",
            status_code=303,
        )

    # Không tạo được gì → quay lại preview
    return templates.TemplateResponse(
        "pages/projects/import_preview.html",
        {
            "request": request,
            "title": "Xem trước import dự án",
            "me": me,
            "company_code": company_code,
            "payload_json": payload,
            "preview": json.loads(payload),
            "err": errors,
        },
        status_code=400,
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

    # NEW: auction config (extras.auction) từ Service A
    auction_cfg = None
    # NEW: bid_ticket config (extras.settings.bid_ticket) từ Service A
    bid_ticket_cfg = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            # 1) Lấy project
            st, data = await _get_json(
                client,
                EP_DETAIL.format(project_id=project_id),
                {"Authorization": f"Bearer {token}"},
            )
            if st == 200 and isinstance(data, dict):
                project = data
            else:
                load_err = f"Không tải được dự án (HTTP {st})."

            # 1b) Lấy auction_config (extras.auction)
            if project:
                cfg_st, cfg = await _get_json(
                    client,
                    EP_AUCTION_CONFIG.format(project_id=project_id),
                    {"Authorization": f"Bearer {token}"},
                )
                if cfg_st == 200 and isinstance(cfg, dict):
                    auction_cfg = cfg.get("auction") or {}
                else:
                    auction_cfg = None

            # 1c) Lấy bid_ticket_config (extras.settings.bid_ticket)
            if project:
                bt_st, bt = await _get_json(
                    client,
                    EP_BID_TICKET_CONFIG.format(project_id=project_id),
                    {"Authorization": f"Bearer {token}"},
                )
                if bt_st == 200 and isinstance(bt, dict):
                    # API A trả: {"settings": {"bid_ticket": {"show_price_step": true}}}
                    bid_ticket_cfg = ((bt.get("settings") or {}).get("bid_ticket") or {})
                else:
                    bid_ticket_cfg = None

            # 2) Nếu có project_code thì lấy danh sách lô theo project_code
            if project and project.get("project_code"):
                # ✅ refactor: gọi helper nhưng phải y hệt call cũ (Authorization Bearer)
                lst_st, lst = await sa_list_lots_by_project_code(
                    client,
                    token=token,
                    project_code=project["project_code"],
                    size=1000,
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
            "auction_cfg": auction_cfg,  # NEW
            "load_err": load_err,
            "bid_ticket_cfg": bid_ticket_cfg,  # NEW
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

    action = (action or "").lower().strip()
    ep = EP_ENABLE if action == "enable" else EP_DISABLE if action == "disable" else None
    redir = (next or "/projects").strip() or "/projects"

    if not ep:
        sep = "&" if "?" in redir else "?"
        return RedirectResponse(url=f"{redir}{sep}err=bad_action&err_msg={quote('Thao tác không hợp lệ.')}", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
        st, data = await _post_json(
            client, ep.format(project_id=project_id), {"Authorization": f"Bearer {token}"}, None
        )

    if st == 200:
        sep = "&" if "?" in redir else "?"
        return RedirectResponse(url=f"{redir}{sep}msg=toggled", status_code=303)

    # FAIL -> đẩy msg về UI
    err_msg, err_hint, err_fields = _pack_toggle_error(st, data)

    sep = "&" if "?" in redir else "?"
    url = (
        f"{redir}{sep}err=toggle_failed"
        f"&err_code={st}"
        f"&err_msg={quote(err_msg)}"
    )
    if err_hint:
        url += f"&err_hint={quote(err_hint)}"
    if err_fields:
        url += f"&err_fields={quote(err_fields)}"

    return RedirectResponse(url=url, status_code=303)


# =========================
# 6) DATA CHO DROPDOWN DỰ ÁN (ACTIVE, theo scope công ty)
# =========================
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
    params: list[tuple[str, str | int]] = [("company_code", company_code), ("page", page), ("size", size)]
    if status:
        params.append(("status", status))
    if q:
        params.append(("q", q))

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.get(EP_PUBLIC_PROJECTS, params=params, headers={"Authorization": f"Bearer {token}"})
        if r.status_code != 200:
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
            r = await client.get(
                EP_PUBLIC_PROJECTS,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "msg": str(e)}, status_code=502)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "upstream_5xx", "msg": r.text[:300]}, status_code=502)
    if r.status_code != 200:
        return JSONResponse({"error": "upstream", "status": r.status_code}, status_code=502)

    js = r.json() or {}
    items = js.get("data") or js.get("items") or js
    if not isinstance(items, list):
        items = []

    data = []
    for p in items:
        code = (p or {}).get("project_code") or (p or {}).get("code")
        name = (p or {}).get("name") or code
        if code:
            data.append({"project_code": code, "name": name})

    return JSONResponse({"data": data}, status_code=200)


@router.get("/api/projects/options")
async def projects_options(
    request: Request,
    status: str = "ACTIVE",
    company_code: str | None = None,
):
    """
    Trả về options dự án cho FE: { options: [{project_code, name}] }
    - Ưu tiên gọi endpoint public của Service A:
      /api/v1/projects/public?company_code=...&status=ACTIVE&page=1&size=1000
    - Nếu không có company_code, Service A sẽ suy ra từ token (nếu hỗ trợ).
    """
    params = {"status": status, "page": 1, "size": 1000}
    if company_code:
        params["company_code"] = company_code

    url = f"{SERVICE_A_BASE_URL}{EP_PUBLIC_PROJECTS}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params, headers=_auth_headers(request))
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Upstream A error {r.status_code}: {r.text}")
        data = r.json() or {}
        items = data.get("data") or data.get("items") or data.get("rows") or []
        options = [
            {
                "project_code": i.get("project_code") or i.get("code"),
                "name": i.get("name") or i.get("project_name") or "",
            }
            for i in items
            if (i.get("project_code") or i.get("code"))
        ]
        return {"options": options}
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach Service A: {e}") from e


# =========================
# 7) DEADLINES (POST từ màn detail)
# =========================
@router.post("/{project_id}/deadlines")
async def update_project_deadlines(
    request: Request,
    project_id: int = Path(...),
    dossier_deadline_at: str = Form(""),     # FE: hạn bán hồ sơ
    deposit_deadline_at: str = Form(""),     # FE: hạn nhận tiền đặt trước
):
    """
    Cập nhật 2 deadline của dự án (Service B → Service A):
    - dossier_deadline_at  → application_deadline_at
    - deposit_deadline_at  → deposit_deadline_at
    """

    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url=f"/login?next=/projects/{project_id}",
            status_code=303,
        )

    # Rỗng -> None
    dossier_v = (dossier_deadline_at or "").strip() or None
    deposit_v = (deposit_deadline_at or "").strip() or None

    # SERVICE A EXPECTS EXACT FIELDS ↓↓↓
    payload = {
        "application_deadline_at": dossier_v,
        "deposit_deadline_at": deposit_v,
    }

    print("====== [DEBUG] SERVICE B → A DEADLINES PAYLOAD ======")
    print(payload)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_DEADLINES.format(project_id=project_id),
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:
                detail = r.text

            print("⚠️ DEADLINE UPDATE FAILED:", detail)

            return RedirectResponse(
                url=f"/projects/{project_id}?err=deadlines_update_failed",
                status_code=303,
            )

    except Exception as e:
        print("🔥 EXCEPTION update_project_deadlines:", e)
        return RedirectResponse(
            url=f"/projects/{project_id}?err=deadlines_update_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/projects/{project_id}?msg=deadlines_updated",
        status_code=303,
    )


# =========================
# 8) AUCTION MODE (PER_LOT / PER_SQM)
# =========================
@router.post("/{project_id}/auction-mode")
async def update_project_auction_mode(
    request: Request,
    project_id: int = Path(...),
    auction_mode_per_sqm: bool = Form(False),
):
    """
    Cập nhật cách tính tiền khi đấu giá cho dự án:
    - checkbox OFF → auction_mode = 'PER_LOT'
    - checkbox ON  → auction_mode = 'PER_SQM'
    """

    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url=f"/login?next=/projects/{project_id}",
            status_code=303,
        )

    mode = "PER_SQM" if auction_mode_per_sqm else "PER_LOT"
    payload = {"auction_mode": mode}

    print("====== [DEBUG] SERVICE B → A AUCTION MODE PAYLOAD ======")
    print("project_id =", project_id)
    print("payload =", payload)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_AUCTION_MODE.format(project_id=project_id),
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:
                detail = r.text

            print("⚠️ AUCTION MODE UPDATE FAILED:", detail)
            return RedirectResponse(
                url=f"/projects/{project_id}?err=auction_mode_update_failed",
                status_code=303,
            )

    except Exception as e:
        print("🔥 EXCEPTION update_project_auction_mode:", e)
        return RedirectResponse(
            url=f"/projects/{project_id}?err=auction_mode_update_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/projects/{project_id}?msg=auction_mode_updated",
        status_code=303,
    )


# =========================
# 9) AUCTION CONFIG (Ngày đấu / Tỉnh thành / Địa điểm)
# =========================
@router.post("/{project_id}/auction-config")
async def update_project_auction_config(
    request: Request,
    project_id: int = Path(...),
    auction_at: str = Form(""),        # dd/mm/yyyy HH:MM:SS (giờ VN) hoặc ISO (tuỳ FE)
    province_city: str = Form(""),
    venue: str = Form(""),
):
    """
    Cập nhật thông tin phiên đấu giá (lưu vào projects.extras.auction) thông qua Service A:
    PUT /api/v1/projects/{project_id}/auction_config

    Service A expects ISO datetime string or null for auction_at.
    Ở FE bạn đang nhập dd/mm/yyyy HH:MM:SS giống deadlines, nên ở đây:
    - nếu value rỗng -> None
    - nếu value đã là ISO -> gửi luôn
    - nếu là dd/mm/yyyy HH:MM:SS -> convert sang ISO +07:00
    """

    token = get_access_token(request)
    if not token:
        return RedirectResponse(url=f"/login?next=/projects/{project_id}", status_code=303)

    def _to_iso_vn(s: str | None) -> str | None:
        s = (s or "").strip()
        if not s:
            return None

        # nếu đã là ISO (có T) thì giữ nguyên
        if "T" in s:
            return s

        # parse dd/mm/yyyy HH:MM:SS
        # ví dụ: 27/01/2026 17:00:00
        try:
            import datetime as _dt
            dt = _dt.datetime.strptime(s, "%d/%m/%Y %H:%M:%S")
            # gắn offset +07:00 thành ISO
            return dt.replace(tzinfo=_dt.timezone(_dt.timedelta(hours=7))).isoformat()
        except Exception:
            # nếu sai format thì gửi nguyên để A báo lỗi (đỡ silent)
            return s

    payload = {
        "auction_at": _to_iso_vn(auction_at),
        "province_city": (province_city or "").strip() or None,
        "venue": (venue or "").strip() or None,
    }

    print("====== [DEBUG] SERVICE B → A AUCTION CONFIG PAYLOAD ======")
    print("project_id =", project_id)
    print("payload =", payload)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_AUCTION_CONFIG.format(project_id=project_id),
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            print("⚠️ AUCTION CONFIG UPDATE FAILED:", detail)
            return RedirectResponse(
                url=f"/projects/{project_id}?err=auction_config_update_failed",
                status_code=303,
            )

    except Exception as e:
        print("🔥 EXCEPTION update_project_auction_config:", e)
        return RedirectResponse(
            url=f"/projects/{project_id}?err=auction_config_update_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/projects/{project_id}?msg=auction_config_updated",
        status_code=303,
    )


@router.post("/{project_id}/bid-ticket-config")
async def update_project_bid_ticket_config(
    request: Request,
    project_id: int = Path(...),
    show_price_step_raw: str | None = Form(None),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url=f"/login?next=/projects/{project_id}", status_code=303)

    # checkbox checked -> có field; unchecked -> None
    show_price_step = True if (show_price_step_raw is not None) else False
    payload = {"show_price_step": show_price_step}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_BID_TICKET_CONFIG.format(project_id=project_id),
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code != 200:
            return RedirectResponse(
                url=f"/projects/{project_id}?err=bid_ticket_config_update_failed",
                status_code=303,
            )
    except Exception:
        return RedirectResponse(
            url=f"/projects/{project_id}?err=bid_ticket_config_update_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/projects/{project_id}?msg=bid_ticket_config_updated",
        status_code=303,
    )

# =========================
# 10) UPDATE BASIC INFO (name / location / description / status)
# =========================
@router.post("/{project_id}/update")
async def update_project_basic_info(
    request: Request,
    project_id: int = Path(...),
    name: str = Form(""),
    location: str = Form(""),
    description: str = Form(""),
    status: str = Form(""),  # optional: ACTIVE|INACTIVE|CLOSED (nếu FE có gửi)
):
    """
    Update thông tin cơ bản của dự án (Service B → Service A):
    - Service A endpoint: PUT /api/v1/projects/{project_id}
    - Fields hỗ trợ bên A: name, location, description, status (và vài field khác)
    """

    token = get_access_token(request)
    if not token:
        return RedirectResponse(url=f"/login?next=/projects/{project_id}", status_code=303)

    # Build payload: chỉ gửi field nào có value khác "" (để khỏi ghi đè thành null ngoài ý muốn)
    payload: dict = {}

    n = (name or "").strip()
    if n != "":
        payload["name"] = n

    loc = (location or "").strip()
    if loc != "":
        payload["location"] = loc

    desc = (description or "").strip()
    if desc != "":
        payload["description"] = desc

    st = (status or "").strip().upper()
    if st in ("ACTIVE", "INACTIVE", "CLOSED"):
        payload["status"] = st
    elif st != "":
        # Nếu FE gửi status lạ thì coi như lỗi form, khỏi gọi A
        return RedirectResponse(
            url=f"/projects/{project_id}?err=project_update_failed",
            status_code=303,
        )

    # Nếu không có gì để update thì thôi
    if not payload:
        return RedirectResponse(url=f"/projects/{project_id}?msg=project_updated", status_code=303)

    print("====== [DEBUG] SERVICE B → A PROJECT UPDATE PAYLOAD ======")
    print("project_id =", project_id)
    print("payload =", payload)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_UPDATE_PROJ.format(pid=project_id),
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            print("⚠️ PROJECT UPDATE FAILED:", detail)
            return RedirectResponse(
                url=f"/projects/{project_id}?err=project_update_failed",
                status_code=303,
            )

    except Exception as e:
        print("🔥 EXCEPTION update_project_basic_info:", e)
        return RedirectResponse(
            url=f"/projects/{project_id}?err=project_update_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/projects/{project_id}?msg=project_updated",
        status_code=303,
    )


# (Optional) JSON API cho AJAX (nếu sau này bạn muốn update inline không reload)
@router.put("/{project_id}/api/update", response_class=JSONResponse)
async def api_update_project_basic_info(
    request: Request,
    project_id: int = Path(...),
):
    """
    JSON API (Service B → Service A) để update name/location/description/status.
    Body JSON ví dụ:
      {"name":"...", "location":"...", "description":"...", "status":"ACTIVE"}
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        body = {}

    if not isinstance(body, dict):
        body = {}

    # Whitelist fields
    payload: dict = {}
    for k in ("name", "location", "description", "status"):
        if k in body:
            v = body.get(k)
            if isinstance(v, str):
                v = v.strip()
            payload[k] = v if v != "" else None

    # Validate status nếu có
    if "status" in payload and payload["status"] is not None:
        st = str(payload["status"]).strip().upper()
        if st not in ("ACTIVE", "INACTIVE", "CLOSED"):
            return JSONResponse({"ok": False, "error": "invalid_status"}, status_code=400)
        payload["status"] = st

    if not payload:
        return JSONResponse({"ok": True, "data": None}, status_code=200)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_UPDATE_PROJ.format(pid=project_id),
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            return JSONResponse(
                {"ok": False, "error": "upstream_error", "status": r.status_code, "detail": detail},
                status_code=502,
            )

        js = r.json() if r.content else None
        return JSONResponse({"ok": True, "data": js}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)

# đặt ở routers/projects.py (Service B)

from typing import Optional, Dict, Any, List
from fastapi import Request, Query
from fastapi.responses import JSONResponse
import httpx

@router.get("/options/listing_projects", response_class=JSONResponse)
async def listing_projects(
    request: Request,
    status: str = Query("ALL", description="ACTIVE|INACTIVE|ALL"),
    q: Optional[str] = Query(None, description="search by code/name (optional)"),
    size: int = Query(1000, ge=1, le=1000),
):
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    st = (status or "ALL").strip().upper()
    if st not in ("ACTIVE", "INACTIVE", "ALL"):
        st = "ALL"

    params: Dict[str, Any] = {"page": 1, "size": size}
    if st != "ALL":
        params["status"] = st
    if q:
        params["q"] = q

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
            r = await client.get(
                EP_LIST,  # "/api/v1/projects"
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as e:
        return JSONResponse({"error": "upstream_error", "msg": str(e)}, status_code=502)

    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code >= 500:
        return JSONResponse({"error": "upstream_5xx", "msg": r.text[:300]}, status_code=502)
    if r.status_code != 200:
        return JSONResponse({"error": "upstream", "status": r.status_code, "detail": r.text[:300]}, status_code=502)

    js = r.json() or {}
    items = js.get("data") or []
    if not isinstance(items, list):
        items = []

    data: List[Dict[str, Any]] = []
    for p in items:
        pp = p or {}

        # ✅ NEW: giữ lại id để UI export hoá đơn dùng project_id
        pid = pp.get("id", None)
        if pid is None:
            pid = pp.get("project_id", None)
        try:
            pid = int(pid) if pid is not None else None
        except Exception:
            pid = None

        code = (pp.get("project_code") or pp.get("code") or "").strip()
        name = (pp.get("name") or "").strip()
        if not code:
            continue

        data.append(
            {
                "id": pid,  # ✅ thêm field này
                "project_code": code,
                "name": name,
                "status": (pp.get("status") or "").strip(),
            }
        )

    return JSONResponse({"data": data}, status_code=200)
