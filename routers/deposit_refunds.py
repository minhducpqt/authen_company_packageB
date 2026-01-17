# routers/deposit_refunds.py  (Service B)
from __future__ import annotations

import os
from typing import Any, Dict, Optional, List, Tuple

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction:refunds"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# =========================================================
# Logging / errors
# =========================================================
def _log(msg: str):
    print(f"[DEPOSIT_REFUNDS_B] {msg}")


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


# =========================================================
# HTTP helpers
# =========================================================
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


async def _post_json(
    path: str,
    token: str,
    params: Dict[str, Any] | None = None,
    json_body: Any | None = None,
) -> Any:
    url = SERVICE_A_BASE_URL.rstrip("/") + path
    _log(f"POST {url} params={params}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            url,
            params=params,
            json=json_body,
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


async def _get_bytes(
    path: str,
    token: str,
    params: Dict[str, Any] | None = None,
) -> Tuple[int, bytes, Dict[str, str]]:
    url = SERVICE_A_BASE_URL.rstrip("/") + path
    _log(f"GET(BYTES) {url} params={params}")
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
    headers = {k: v for k, v in r.headers.items()}
    return r.status_code, r.content, headers


# =========================================================
# Projects helpers (keep existing behavior)
# =========================================================
def _parse_projects(js: Any) -> List[Dict[str, Any]]:
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


def _find_project_id_by_code(projects: List[Dict[str, Any]], project_code: str) -> Optional[int]:
    if not project_code:
        return None
    for p in projects or []:
        code = p.get("project_code") or p.get("code") or ""
        if str(code) == str(project_code):
            try:
                return int(p.get("id"))
            except Exception:
                return None
    return None


def _norm_score_level(s: str) -> str:
    s = (s or "").upper().strip()
    return s if s in ("ALL", "LOW", "MEDIUM", "HIGH") else "ALL"


def _norm_eligible(s: str) -> str:
    """
    UI có thể dùng: ELIGIBLE | EXCLUDED | ALL
    (khớp với A)
    """
    s = (s or "").upper().strip()
    return s if s in ("ELIGIBLE", "EXCLUDED", "ALL") else "ELIGIBLE"


# =========================================================
# 1) PAGE: Refund candidates
#    A: GET /api/v1/auction/refunds
# =========================================================
@router.get("/auction/refunds", response_class=HTMLResponse)
async def refund_candidates_page(
    request: Request,
    project: str = Query("", alias="project"),
    score_level: str = Query("ALL", alias="score_level"),  # UI default ALL
    eligible: str = Query("ELIGIBLE", alias="eligible"),   # optional (A supports)
    q: str = Query(""),
    page: int = Query(1, ge=1),
    size: int = Query(500, ge=1, le=5000),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/public/login", status_code=302)

    error = None
    projects: List[Dict[str, Any]] = []
    data = None
    project_id = None

    score_level = _norm_score_level(score_level)
    eligible = _norm_eligible(eligible)

    # Load projects (giữ hành vi cũ)
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

    project_id = _find_project_id_by_code(projects, project)

    # Load refunds only when project selected
    if project_id:
        try:
            params = {
                "project_id": int(project_id),
                "eligible": eligible,   # ✅ A supports
                "q": q or "",
                "page": page,
                "size": size,
            }

            # score_level: chỉ gửi nếu bạn đã bổ sung filter này ở A
            # (Nếu A chưa hỗ trợ, có thể comment 2 dòng dưới)
            if score_level and score_level != "ALL":
                params["score_level"] = score_level

            data = await _get_json("/api/v1/auction/refunds", token, params=params)
        except ServiceAError as e:
            error = {"status": e.status, "body": e.body}
            data = None

    return templates.TemplateResponse(
        "auction/auction_refunds.html",  # ✅ đúng path template
        {
            "request": request,
            "projects": projects,
            "project": project,
            "project_id": project_id,
            "score_level": score_level,
            "eligible": eligible,
            "q": q,
            "page": page,
            "size": size,
            "data": data,
            "error": error,
        },
    )


# =========================================================
# 2) AJAX: Detail popup
#    A: GET /api/v1/auction/refunds/{id}/detail
# =========================================================
@router.get("/auction/refunds/detail.json")
async def refund_candidate_detail_json(
    request: Request,
    candidate_id: int = Query(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "detail": "Not authenticated"}, status_code=401)

    try:
        js = await _get_json(f"/api/v1/auction/refunds/{int(candidate_id)}/detail", token, params=None)
        return JSONResponse(js)
    except ServiceAError as e:
        return JSONResponse({"ok": False, "status": e.status, "body": e.body}, status_code=500)


# =========================================================
# 3) Rebuild snapshot (A: POST /api/v1/auction/refunds/rebuild)
# =========================================================
@router.post("/auction/refunds/rebuild")
async def rebuild_refund_candidates(request: Request):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"ok": False, "detail": "Not authenticated"}, status_code=401)

    form = await request.form()
    project_id = (form.get("project_id") or "").strip()
    if not project_id:
        return JSONResponse({"ok": False, "detail": "project_id is required"}, status_code=400)

    try:
        js = await _post_json("/api/v1/auction/refunds/rebuild", token, params={"project_id": int(project_id)})
        return JSONResponse({"ok": True, "data": js})
    except ServiceAError as e:
        return JSONResponse({"ok": False, "status": e.status, "body": e.body}, status_code=500)


# =========================================================
# 4) Export XLSX proxy
#    A: GET /api/v1/auction/refunds/export.xlsx
# =========================================================
@router.get("/auction/refunds/export.xlsx")
async def export_refunds_xlsx_proxy(
    request: Request,
    project_id: int = Query(..., ge=1),
    eligible: str = Query("ELIGIBLE"),
    score_level: str = Query("ALL"),
    q: str = Query(""),
):
    token = get_access_token(request)
    if not token:
        return RedirectResponse(url="/public/login", status_code=302)

    eligible = _norm_eligible(eligible)
    score_level = _norm_score_level(score_level)

    params: Dict[str, Any] = {
        "project_id": int(project_id),
        "eligible": eligible,
    }

    # score_level/q: chỉ gửi nếu A hỗ trợ (A có thể ignore)
    if score_level and score_level != "ALL":
        params["score_level"] = score_level
    if q:
        params["q"] = q

    try:
        status, content, headers = await _get_bytes(
            "/api/v1/auction/refunds/export.xlsx",
            token,
            params=params,
        )
        if status >= 400:
            try:
                import json

                js = json.loads(content.decode("utf-8", errors="ignore"))
            except Exception:
                js = {"raw": content[:400].decode("utf-8", errors="ignore")}
            raise ServiceAError(status, js)

        cd = headers.get("content-disposition") or headers.get("Content-Disposition")
        resp_headers = {
            "Content-Disposition": cd
            or f'attachment; filename="refunds_project_{project_id}.xlsx"'
        }

        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=resp_headers,
        )
    except ServiceAError as e:
        return JSONResponse({"ok": False, "status": e.status, "body": e.body}, status_code=500)
