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
from routers.lots import sa_create_lot, sa_list_lots_by_project_code, sa_bulk_create_lots

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
EP_BID_STEP_POLICY  = "/api/v1/projects/{project_id}/bid_step_policy"  # <-- NEW
EP_GROUP_AUCTION_CONFIG = "/api/v1/projects/{project_id}/group_auction_config"  # <-- NEW
EP_GROUP_AUCTION_DEPOSIT_GROUPS = "/api/v1/projects/{project_id}/group_auction/deposit_groups"  # <-- NEW
EP_GROUP_AUCTION_READINESS = "/api/v1/projects/{project_id}/group_auction/readiness"  # <-- NEW

EP_PRODUCT_TYPES      = "/api/v1/projects/product_types"                 # NEW
EP_PRODUCT_TYPE_ITEMS = "/api/v1/projects/product_types/{product_type}"  # NEW

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

async def _put_json(client: httpx.AsyncClient, url: str, headers: dict, payload: dict | None):
    r = await client.put(url, headers=headers, json=payload or {})
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
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        return RedirectResponse(url="/login?next=/projects/import", status_code=303)

    # chặn force_replace nếu FE cũ gửi
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
            {"request": request, "title": "Nhập dự án từ Excel", "me": me, "err": "Payload không hợp lệ."},
            status_code=400,
        )

    projects = data.get("projects") or []
    lots = data.get("lots") or []

    errors: list[str] = []
    created_codes: list[str] = []

    headers = {"Authorization": f"Bearer {token}", "X-Company-Code": company_code}

    def _pretty(obj) -> str:
        try:
            if isinstance(obj, str):
                return obj
            return json.dumps(obj, ensure_ascii=False)
        except Exception:
            return str(obj)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=60.0) as client:
        for p in projects:
            code = (p.get("project_code") or "").strip()
            name = (p.get("name") or "").strip()

            if not code or not name:
                errors.append("Thiếu project_code hoặc name.")
                continue

            # 1) create project
            proj_body = {
                "project_code": code,
                "name": name,
                "description": p.get("description") or None,
                "location": p.get("location") or None,
                "status": "INACTIVE",
            }
            r = await client.post(EP_CREATE_PROJ, json=proj_body, headers=headers)

            if r.status_code == 200:
                created_codes.append(code)
            elif r.status_code == 409:
                errors.append(f"Dự án {code}: đã tồn tại, không cho phép ghi đè.")
                # project lỗi -> bỏ luôn lots của project này
                continue
            else:
                try:
                    js = r.json() if r.content else {}
                except Exception:
                    js = {}
                msg = (js or {}).get("detail") or (js or {}).get("message") or ""
                errors.append(f"Dự án {code}: tạo thất bại (HTTP {r.status_code}) {msg}")
                continue

            # 2) gom lots theo project_code rồi gọi BULK (atomic theo project)
            proj_lots = [
                l for l in lots
                if (l.get("project_code") or "").strip().upper() == code.upper()
            ]
            if not proj_lots:
                continue

            bulk_lots: list[dict] = []
            for l in proj_lots:
                lot_code = (l.get("lot_code") or "").strip()
                # nếu thiếu lot_code, tự báo lỗi rõ ràng trước khi gọi A
                if not lot_code:
                    errors.append(f"Dự án {code}: có lô bị thiếu lot_code trong file Excel.")
                    continue

                bulk_lots.append(
                    {
                        "lot_code": lot_code,
                        "name": l.get("name") or None,
                        "description": l.get("description") or None,
                        "starting_price": l.get("starting_price"),
                        "deposit_amount": l.get("deposit_amount"),
                        "bid_step_vnd": l.get("bid_step_vnd"),
                        "area": l.get("area"),
                        "status": "AVAILABLE",
                    }
                )

            # nếu tất cả lot đều lỗi lot_code rỗng -> khỏi gọi bulk
            if not bulk_lots:
                continue

            st_bulk, js_bulk = await sa_bulk_create_lots(
                client,
                token=token,                 # ✅ bắt buộc vì helper bạn định nghĩa token: str
                project_code=code,
                lots=bulk_lots,
                company_code=company_code,
                headers=headers,
            )

            if st_bulk != 200:
                detail = (js_bulk or {}).get("detail", js_bulk) if isinstance(js_bulk, dict) else js_bulk
                errors.append(
                    f"Dự án {code}: bulk lots thất bại (HTTP {st_bulk}) - { _pretty(detail) }"
                )

    # ✅ yêu cầu mới của bạn:
    # - nếu có lỗi: đứng tại preview show lỗi
    if errors:
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

    # - nếu không lỗi: redirect như cũ
    return RedirectResponse(
        url=f"/projects?msg=import_ok&c={len(created_codes)}",
        status_code=303,
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
            return {
                "project_code": code,
                "name": name,
                "status": x.get("status"),
                "id": x.get("id") or x.get("project_id"),
                "group_auction": x.get("group_auction") or {
                    "enabled": False,
                    "registration_mode": "NORMAL",
                    "ticket_mode": None,
                },
            }

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
            data.append({
                "project_code": code,
                "name": name,
                "group_auction": (p or {}).get("group_auction") or {
                    "enabled": False,
                    "registration_mode": "NORMAL",
                    "ticket_mode": None,
                },
            })

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
                "id": i.get("id") or i.get("project_id"),
                "project_code": i.get("project_code") or i.get("code"),
                "name": i.get("name") or i.get("project_name") or "",
                "group_auction": i.get("group_auction") or {
                    "enabled": False,
                    "registration_mode": "NORMAL",
                    "ticket_mode": None,
                },
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
                "group_auction": pp.get("group_auction") or {
                    "enabled": False,
                    "registration_mode": "NORMAL",
                    "ticket_mode": None,
                },
            }
        )

    return JSONResponse({"data": data}, status_code=200)

@router.get("/api/product_types", response_class=JSONResponse)
async def api_product_types(request: Request):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.get(
                EP_PRODUCT_TYPES,
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code != 200:
            return JSONResponse(
                {"error": "upstream", "status": r.status_code, "detail": (r.text or "")[:300]},
                status_code=502,
            )
        return JSONResponse(r.json() or {}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": "exception", "message": str(e)}, status_code=500)


@router.get("/api/product_types/{product_type}", response_class=JSONResponse)
async def api_product_type_items(request: Request, product_type: str = Path(...)):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    pt = (product_type or "").strip().upper()
    if not pt:
        return JSONResponse({"error": "bad_product_type"}, status_code=400)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.get(
                EP_PRODUCT_TYPE_ITEMS.format(product_type=pt),
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code != 200:
            return JSONResponse(
                {"error": "upstream", "status": r.status_code, "detail": (r.text or "")[:300]},
                status_code=502,
            )
        return JSONResponse(r.json() or {}, status_code=200)
    except Exception as e:
        return JSONResponse({"error": "exception", "message": str(e)}, status_code=500)


@router.post("/{project_id}/product-type")
async def update_project_product_type(
    request: Request,
    project_id: int = Path(...),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        body = {}

    pt = (body.get("product_type") or "").strip().upper()
    if not pt:
        return JSONResponse({"ok": False, "error": "missing_product_type"}, status_code=400)

    payload = {"product_type": pt}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                f"/api/v1/projects/{project_id}/product_type",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {"ok": False, "error": "upstream_error", "detail": r.text},
                status_code=502,
            )

        return JSONResponse({"ok": True})

    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)



# =========================
# 10B) GROUP AUCTION CONFIG / DEPOSIT GROUPS (Service B → Service A)
# =========================
def _normal_group_auction_config() -> dict:
    return {
        "enabled": False,
        "registration_mode": "NORMAL",
        "ticket_mode": None,
    }


@router.get("/{project_id}/group-auction-config", response_class=JSONResponse)
async def get_project_group_auction_config_b(
    request: Request,
    project_id: int = Path(...),
):
    """
    Proxy GET cấu hình đấu giá theo nhóm cọc.
    B -> A: GET /api/v1/projects/{project_id}/group_auction_config
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.get(
                EP_GROUP_AUCTION_CONFIG.format(project_id=project_id),
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


@router.put("/{project_id}/group-auction-config", response_class=JSONResponse)
async def update_project_group_auction_config_b(
    request: Request,
    project_id: int = Path(...),
):
    """
    Proxy PUT cấu hình đấu giá theo nhóm cọc.
    Body:
      {
        "enabled": true|false,
        "registration_mode": "NORMAL"|"GROUP_AUCTION",
        "ticket_mode": "PRE_SESSION"|"BLANK_TICKET"
      }
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

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_GROUP_AUCTION_CONFIG.format(project_id=project_id),
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


@router.post("/{project_id}/group-auction-config")
async def update_project_group_auction_config_form_b(
    request: Request,
    project_id: int = Path(...),
    enabled_raw: str | None = Form(None),
    ticket_mode: str = Form("PRE_SESSION"),
):
    """
    Form submit từ trang detail.
    - checkbox enabled_raw có mặt => enabled=true
    - ticket_mode: PRE_SESSION | BLANK_TICKET
    """
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url=f"/login?next=/projects/{project_id}", status_code=303)

    enabled = enabled_raw is not None
    tm = (ticket_mode or "PRE_SESSION").strip().upper()
    if tm not in ("PRE_SESSION", "BLANK_TICKET"):
        tm = "PRE_SESSION"

    payload = {
        "enabled": enabled,
        "registration_mode": "GROUP_AUCTION" if enabled else "NORMAL",
        "ticket_mode": tm if enabled else None,
    }

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_GROUP_AUCTION_CONFIG.format(project_id=project_id),
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return RedirectResponse(
                url=f"/projects/{project_id}?err=group_auction_config_update_failed",
                status_code=303,
            )

    except Exception:
        return RedirectResponse(
            url=f"/projects/{project_id}?err=group_auction_config_update_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/projects/{project_id}?msg=group_auction_config_updated",
        status_code=303,
    )


@router.get("/{project_id}/group-auction/deposit-groups", response_class=JSONResponse)
async def get_project_group_auction_deposit_groups_b(
    request: Request,
    project_id: int = Path(...),
):
    """
    Proxy GET danh sách nhóm cọc tự sinh từ lots + config tiền hồ sơ.
    B -> A: GET /api/v1/projects/{project_id}/group_auction/deposit_groups
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.get(
                EP_GROUP_AUCTION_DEPOSIT_GROUPS.format(project_id=project_id),
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


@router.put("/{project_id}/group-auction/deposit-groups", response_class=JSONResponse)
async def update_project_group_auction_deposit_groups_b(
    request: Request,
    project_id: int = Path(...),
):
    """
    Proxy PUT lưu tiền hồ sơ cho từng nhóm cọc.
    Body:
      {
        "groups": [
          {
            "deposit_amount_vnd": 200000000,
            "dossier_fee_vnd": 100000,
            "group_name": "Nhóm cọc 200 triệu",
            "is_active": true
          }
        ]
      }
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

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_GROUP_AUCTION_DEPOSIT_GROUPS.format(project_id=project_id),
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


@router.post("/{project_id}/group-auction/deposit-groups")
async def update_project_group_auction_deposit_groups_form_b(
    request: Request,
    project_id: int = Path(...),
    groups_json: str = Form(""),
):
    """
    Form submit từ trang detail.
    groups_json là JSON string:
      {"groups":[...]}
    hoặc list trực tiếp:
      [...]
    """
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url=f"/login?next=/projects/{project_id}", status_code=303)

    try:
        obj = json.loads(groups_json or "{}")
        if isinstance(obj, list):
            payload = {"groups": obj}
        elif isinstance(obj, dict):
            payload = obj if "groups" in obj else {"groups": []}
        else:
            payload = {"groups": []}
    except Exception:
        return RedirectResponse(
            url=f"/projects/{project_id}?err=group_auction_groups_bad_json",
            status_code=303,
        )

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_GROUP_AUCTION_DEPOSIT_GROUPS.format(project_id=project_id),
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return RedirectResponse(
                url=f"/projects/{project_id}?err=group_auction_groups_update_failed",
                status_code=303,
            )

    except Exception:
        return RedirectResponse(
            url=f"/projects/{project_id}?err=group_auction_groups_update_failed",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/projects/{project_id}?msg=group_auction_groups_updated",
        status_code=303,
    )


@router.get("/{project_id}/group-auction/readiness", response_class=JSONResponse)
async def get_project_group_auction_readiness_b(
    request: Request,
    project_id: int = Path(...),
):
    """
    Proxy GET readiness kiểm tra dự án nhóm cọc đã đủ cấu hình chưa.
    B -> A: GET /api/v1/projects/{project_id}/group_auction/readiness
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.get(
                EP_GROUP_AUCTION_READINESS.format(project_id=project_id),
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


# =========================
# 11) BID STEP POLICY CONFIG (Service B → Service A)
# =========================
@router.get("/{project_id}/bid-step-policy", response_class=JSONResponse)
async def get_project_bid_step_policy_b(
    request: Request,
    project_id: int = Path(...),
):
    """
    Proxy GET cấu hình bước giá theo vòng:
    B -> A: GET /api/v1/projects/{project_id}/bid_step_policy
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.get(
                EP_BID_STEP_POLICY.format(project_id=project_id),
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


@router.put("/{project_id}/bid-step-policy", response_class=JSONResponse)
async def update_project_bid_step_policy_b(
    request: Request,
    project_id: int = Path(...),
):
    """
    Proxy PUT toàn bộ cấu hình bước giá theo vòng.
    Body có thể là:
      {
        "default": {...},
        "round_rules": [...]
      }
    hoặc:
      {
        "bid_step_policy": {
          "default": {...},
          "round_rules": [...]
        }
      }
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

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                EP_BID_STEP_POLICY.format(project_id=project_id),
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


@router.post("/{project_id}/bid-step-policy/round-rules", response_class=JSONResponse)
async def add_project_bid_step_round_rule_b(
    request: Request,
    project_id: int = Path(...),
):
    """
    Proxy thêm/cập nhật 1 rule vòng.
    Nếu body không có round_no, Service A sẽ tự thêm vòng kế tiếp.
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

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.post(
                f"/api/v1/projects/{project_id}/bid_step_policy/round_rules",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


@router.put("/{project_id}/bid-step-policy/round-rules/{round_no}", response_class=JSONResponse)
async def update_project_bid_step_round_rule_b(
    request: Request,
    project_id: int = Path(...),
    round_no: int = Path(..., ge=1),
):
    """
    Proxy sửa rule của 1 vòng cụ thể.
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

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.put(
                f"/api/v1/projects/{project_id}/bid_step_policy/round_rules/{int(round_no)}",
                json=body,
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


@router.delete("/{project_id}/bid-step-policy/round-rules/last", response_class=JSONResponse)
async def delete_last_project_bid_step_round_rule_b(
    request: Request,
    project_id: int = Path(...),
):
    """
    Proxy xoá cấu hình vòng cuối cùng.
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.delete(
                f"/api/v1/projects/{project_id}/bid_step_policy/round_rules/last",
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


@router.delete("/{project_id}/bid-step-policy/round-rules/{round_no}", response_class=JSONResponse)
async def delete_project_bid_step_round_rule_b(
    request: Request,
    project_id: int = Path(...),
    round_no: int = Path(..., ge=1),
):
    """
    Proxy xoá cấu hình của 1 vòng cụ thể.
    """
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=10.0) as client:
            r = await client.delete(
                f"/api/v1/projects/{project_id}/bid_step_policy/round_rules/{int(round_no)}",
                headers={"Authorization": f"Bearer {token}"},
            )

        if r.status_code != 200:
            return JSONResponse(
                {
                    "ok": False,
                    "error": "upstream_error",
                    "status": r.status_code,
                    "detail": (r.text or "")[:500],
                },
                status_code=502,
            )

        return JSONResponse(r.json() or {}, status_code=200)

    except Exception as e:
        return JSONResponse({"ok": False, "error": "exception", "message": str(e)}, status_code=500)


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
    # NEW: bid_step_policy (projects.extras.bid_step_policy) từ Service A
    bid_step_policy = None
    # NEW: group_auction config/groups/readiness từ Service A
    group_auction_cfg = None
    group_auction_groups = None
    group_auction_readiness = None

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

            # 1d) Lấy bid_step_policy (extras.bid_step_policy)
            if project:
                bsp_st, bsp = await _get_json(
                    client,
                    EP_BID_STEP_POLICY.format(project_id=project_id),
                    {"Authorization": f"Bearer {token}"},
                )
                if bsp_st == 200 and isinstance(bsp, dict):
                    bid_step_policy = bsp.get("bid_step_policy") or {}
                else:
                    bid_step_policy = None

            # 1e) Lấy group_auction_config
            if project:
                ga_st, ga = await _get_json(
                    client,
                    EP_GROUP_AUCTION_CONFIG.format(project_id=project_id),
                    {"Authorization": f"Bearer {token}"},
                )
                if ga_st == 200 and isinstance(ga, dict):
                    group_auction_cfg = (
                        ga.get("group_auction")
                        or ga.get("data")
                        or project.get("group_auction")
                        or _normal_group_auction_config()
                    )
                else:
                    group_auction_cfg = project.get("group_auction") or _normal_group_auction_config()

            # 1f) Lấy nhóm cọc tự sinh + cấu hình tiền hồ sơ
            if project:
                gag_st, gag = await _get_json(
                    client,
                    EP_GROUP_AUCTION_DEPOSIT_GROUPS.format(project_id=project_id),
                    {"Authorization": f"Bearer {token}"},
                )
                if gag_st == 200 and isinstance(gag, dict):
                    group_auction_groups = gag.get("groups") or gag.get("items") or gag.get("data") or []
                else:
                    group_auction_groups = []

            # 1g) Lấy readiness group auction
            if project:
                gar_st, gar = await _get_json(
                    client,
                    EP_GROUP_AUCTION_READINESS.format(project_id=project_id),
                    {"Authorization": f"Bearer {token}"},
                )
                if gar_st == 200 and isinstance(gar, dict):
                    group_auction_readiness = gar
                else:
                    group_auction_readiness = None

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
            "bid_step_policy": bid_step_policy,  # NEW
            "group_auction_cfg": group_auction_cfg or _normal_group_auction_config(),  # NEW
            "group_auction_groups": group_auction_groups or [],  # NEW
            "group_auction_readiness": group_auction_readiness,  # NEW
        },
    )
