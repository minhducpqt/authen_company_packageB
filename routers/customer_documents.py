# app/routers/customer_documents.py
from __future__ import annotations

import os
from typing import Optional, Dict, Any, List, Tuple

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["customer_documents"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

# ============================================================
# IMPORTANT: ĐƯỜNG DẪN RIÊNG (KHÔNG ĐỤNG /customers/*)
# - Page list:    /_admin/customer-documents
# - Data list:    /_admin/customer-documents/data
# - Page detail:  /_admin/customer-documents/detail
# - Data detail:  /_admin/customer-documents/detail/data
# ============================================================
BASE_PATH = "/_admin/customer-documents"


# ---------- logging helper ----------
def _log(msg: str):
    print(f"[CUST_DOCS_B] {msg}")


def _preview_body(data: Any, limit: int = 300) -> str:
    try:
        import json
        s = json.dumps(data, ensure_ascii=False)
    except Exception:
        s = str(data)
    if len(s) > limit:
        return s[:limit] + "...(truncated)"
    return s


def _unauth():
    return JSONResponse({"error": "unauthorized"}, status_code=401)


# ---------- HTTP helpers ----------
async def _get_json(
    path: str,
    token: str,
    params: Dict[str, Any] | List[Tuple[str, Any]] | None = None,
):
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ GET JSON {url} params={params or {}}")

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
        text_preview = (r.text or "")[:300]
        _log(f"← {r.status_code} {url} text={text_preview}")
        return r.status_code, {"detail": (r.text or "")[:500]}


# ---------- Helper: load ACTIVE projects ----------
async def _load_projects(token: str, project_param: Optional[str]) -> tuple[list[dict], str]:
    """
    Gọi Service A /api/v1/projects để lấy danh sách dự án ACTIVE.
    - project_param: có thể là project_id (chuỗi số) hoặc project_code.
    - Nếu không có, và chỉ có 1 dự án ACTIVE -> auto chọn dự án đó (ưu tiên id).
    Trả về (projects, selected_project_key)
    """
    st, pj = await _get_json(
        "/api/v1/projects",
        token,
        {"status": "ACTIVE", "size": 1000},
    )
    projects: list[dict] = []
    selected = (project_param or "").strip()

    if st == 200 and isinstance(pj, dict):
        projects = pj.get("data") or pj.get("items") or []
        _log(f"_load_projects: got {len(projects)} active projects")

        if not selected and len(projects) == 1:
            pid = projects[0].get("id")
            pcode = projects[0].get("project_code")
            selected = str(pid) if pid is not None else (str(pcode or "").upper())
            _log(f"_load_projects: auto-selected single project={selected}")
    else:
        _log(f"_load_projects: failed st={st} body={pj}")

    return projects, selected


def _pick_project_id(projects: List[dict], selected: str) -> Optional[int]:
    """
    selected có thể là:
    - "123" (project_id)
    - "KIDO6" (project_code)
    """
    if not selected:
        return None

    if selected.isdigit():
        try:
            return int(selected)
        except Exception:
            return None

    sel_code = selected.strip().upper()
    for p in projects or []:
        if (p.get("project_code") or "").strip().upper() == sel_code:
            pid = p.get("id")
            if pid is None:
                return None
            try:
                return int(pid)
            except Exception:
                return None
    return None


# ============================================================
# 4.1 GIẤY TỜ PHẢI NỘP (HTML PAGE)
# ============================================================
@router.get(f"{BASE_PATH}", response_class=HTMLResponse)
async def customer_documents_page(
    request: Request,
    project: Optional[str] = Query(None, description="project_id (recommended) hoặc project_code"),
):
    _log(f"REQ {BASE_PATH} url={request.url}")

    token = get_access_token(request)
    if not token:
        return RedirectResponse(
            url=f"/login?next={BASE_PATH.replace('/', '%2F')}",
            status_code=303,
        )

    projects, selected_project = await _load_projects(token, project)
    project_id = _pick_project_id(projects, selected_project)

    return templates.TemplateResponse(
        "documents/customers_documents.html",
        {
            "request": request,
            "title": "Giấy tờ phải nộp",
            "projects": projects,
            "project": selected_project,
            "project_id": project_id,
            "data_url": f"{BASE_PATH}/data",
            "base_path": BASE_PATH,
        },
    )


# ============================================================
# 4.1 GIẤY TỜ PHẢI NỘP (AJAX JSON DATA)
# ============================================================
@router.get(f"{BASE_PATH}/data", response_class=JSONResponse)
async def customer_documents_data(
    request: Request,
    project: str = Query(..., description="project_id (recommended) hoặc project_code"),
    q: Optional[str] = Query(None, description="Search name/CCCD"),
    doc_status: str = Query("ALL", description="ALL|COMPLETE|MISSING"),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=1000),
    sort: str = Query("-last_deposit_paid_at", description="Sort field, e.g. -last_deposit_paid_at"),
    expose_phone: bool = Query(False, description="Chỉ dùng khi role có PII permission"),
    expose_docs: bool = Query(True, description="true để trả thêm URL giấy tờ (nếu role có quyền)"),
):
    _log(f"REQ {BASE_PATH}/data url={request.url}")

    token = get_access_token(request)
    if not token:
        return _unauth()

    projects, selected_project = await _load_projects(token, project)
    project_id = _pick_project_id(projects, selected_project)
    if not project_id:
        return JSONResponse(
            {"error": "invalid_project", "detail": "project must be project_id or valid project_code"},
            status_code=400,
        )

    params: Dict[str, Any] = {
        "page": page,
        "size": size,
        "sort": sort,
        "doc_status": (doc_status or "ALL").upper(),
        "expose_phone": "true" if expose_phone else "false",
        "expose_docs": "true" if expose_docs else "false",
    }
    if q and q.strip():
        params["q"] = q.strip()

    path = f"/api/v1/admin/projects/{project_id}/customers"
    st, js = await _get_json(path, token, params)

    if st == 401:
        return _unauth()
    if st != 200:
        return JSONResponse(
            {"error": "service_a_failed", "status": st, "body": js},
            status_code=502,
        )

    return JSONResponse(js, status_code=200)


# ============================================================
# 4.1 DETAIL (HTML PAGE)
#   /_admin/customer-documents/detail?project=3&customer_id=2
# ============================================================
@router.get(f"{BASE_PATH}/detail", response_class=HTMLResponse)
async def customer_documents_detail_page(
    request: Request,
    project: str = Query(..., description="project_id (recommended) hoặc project_code"),
    customer_id: int = Query(..., ge=1),
):
    _log(f"REQ {BASE_PATH}/detail url={request.url}")

    token = get_access_token(request)
    if not token:
        next_q = f"{BASE_PATH}/detail?project={project}&customer_id={customer_id}"
        return RedirectResponse(
            url=f"/login?next={next_q.replace('/', '%2F').replace('?', '%3F').replace('&','%26').replace('=','%3D')}",
            status_code=303,
        )

    projects, selected_project = await _load_projects(token, project)
    project_id = _pick_project_id(projects, selected_project)
    if not project_id:
        return RedirectResponse(url=f"{BASE_PATH}", status_code=303)

    return templates.TemplateResponse(
        "documents/customer_documents_detail.html",
        {
            "request": request,
            "title": "Chi tiết giấy tờ",
            "projects": projects,
            "project": selected_project,
            "project_id": project_id,
            "customer_id": customer_id,
            "base_path": BASE_PATH,
            "data_url": f"{BASE_PATH}/detail/data",
            "back_url": f"{BASE_PATH}?project={project_id}",
        },
    )


# ============================================================
# 4.1 DETAIL (AJAX JSON DATA)
#   Proxy to Service A:
#     - detail:      /api/v1/admin/projects/{project_id}/customers/{customer_id}
#     - depositLots: /api/v1/admin/projects/{project_id}/customers/{customer_id}/deposit-lots
# ============================================================
@router.get(f"{BASE_PATH}/detail/data", response_class=JSONResponse)
async def customer_documents_detail_data(
    request: Request,
    project: str = Query(..., description="project_id (recommended) hoặc project_code"),
    customer_id: int = Query(..., ge=1),
    lots_page: int = Query(1, ge=1),
    lots_size: int = Query(200, ge=1, le=1000),
    lots_sort: str = Query("-deposit_paid_at"),
    expose_phone: bool = Query(True),
    expose_docs: bool = Query(True),
):
    _log(f"REQ {BASE_PATH}/detail/data url={request.url}")

    token = get_access_token(request)
    if not token:
        return _unauth()

    projects, selected_project = await _load_projects(token, project)
    project_id = _pick_project_id(projects, selected_project)
    if not project_id:
        return JSONResponse(
            {"error": "invalid_project", "detail": "project must be project_id or valid project_code"},
            status_code=400,
        )

    # 1) Detail
    detail_path = f"/api/v1/admin/projects/{project_id}/customers/{customer_id}"
    st1, detail = await _get_json(
        detail_path,
        token,
        {
            "expose_phone": "true" if expose_phone else "false",
            "expose_docs": "true" if expose_docs else "false",
        },
    )
    if st1 == 401:
        return _unauth()
    if st1 != 200:
        return JSONResponse(
            {"error": "service_a_failed_detail", "status": st1, "body": detail},
            status_code=502,
        )

    # 2) Deposit lots
    lots_path = f"/api/v1/admin/projects/{project_id}/customers/{customer_id}/deposit-lots"
    st2, lots = await _get_json(
        lots_path,
        token,
        {
            "page": lots_page,
            "size": lots_size,
            "sort": lots_sort,
        },
    )
    if st2 == 401:
        return _unauth()
    if st2 != 200:
        return JSONResponse(
            {"error": "service_a_failed_lots", "status": st2, "body": lots},
            status_code=502,
        )

    return JSONResponse(
        {
            "detail": detail,
            "deposit_lots": lots,
        },
        status_code=200,
    )
