from __future__ import annotations

from fastapi import APIRouter, Request, Query, Path
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse, HTMLResponse
import httpx, os

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/invoice-exports", tags=["invoice-exports"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")


def _get_access_token(request: Request) -> str | None:
    return request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)


async def _me(request: Request) -> dict | None:
    acc = _get_access_token(request)
    if not acc:
        return None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            r = await client.get("/auth/me", headers={"Authorization": f"Bearer {acc}"})
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


async def _get_json(client: httpx.AsyncClient, url: str, headers: dict, params: dict | None = None):
    r = await client.get(url, headers=headers, params=params)
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


def _ensure_login(request: Request, next_url: str):
    # đồng bộ style như account.py
    return RedirectResponse(url=f"/login?next={next_url}", status_code=303)


# ============================================================
# SSR PAGE (menu 3.2) - Không tạo file mới
# GET /invoice-exports
# -> render templates/invoices/export.html (bạn sẽ bổ sung UI sau)
# ============================================================
@router.get("", response_class=HTMLResponse)
async def invoice_exports_page(request: Request):
    me = await _me(request)
    if not me:
        return _ensure_login(request, "/invoice-exports")

    role = (me.get("role") or "").upper()

    return templates.TemplateResponse(
        "invoices/export.html",
        {
            "request": request,
            "me": me,
            "role": role,
            "title": "Xuất hoá đơn",
        }
    )


# ============================================================
# API: List logs
# GET /invoice-exports/api/projects/{project_id}/logs?limit=200&target=BKAV
# ============================================================
@router.get("/api/projects/{project_id}/logs")
async def api_list_logs(
    request: Request,
    project_id: int = Path(..., ge=1),
    limit: int = Query(200, ge=1),
    target: str | None = Query(None),
):
    me = await _me(request)
    if not me:
        return _ensure_login(request, f"/invoice-exports?project_id={project_id}")

    acc = _get_access_token(request)
    params = {"limit": limit}
    if target:
        params["target"] = target

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
            st, data = await _get_json(
                client,
                f"/api/v1/invoice-exports/projects/{project_id}/logs",
                {"Authorization": f"Bearer {acc}"},
                params=params,
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    return JSONResponse(status_code=st, content=(data or {}))


# ============================================================
# API: Create log (Export)
# POST /invoice-exports/api/projects/{project_id}/logs
# body: {time_from,time_to,target,vat_rate}
# ============================================================
@router.post("/api/projects/{project_id}/logs")
async def api_create_log(
    request: Request,
    project_id: int = Path(..., ge=1),
):
    me = await _me(request)
    if not me:
        return _ensure_login(request, f"/invoice-exports?project_id={project_id}")

    acc = _get_access_token(request)
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
            st, data = await _post_json(
                client,
                f"/api/v1/invoice-exports/projects/{project_id}/logs",
                {"Authorization": f"Bearer {acc}"},
                payload,
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    return JSONResponse(status_code=st, content=(data or {}))


# ============================================================
# API: Download (stream)
# GET /invoice-exports/api/logs/{log_id}/download
# ============================================================
@router.get("/api/logs/{log_id}/download")
async def api_download(
    request: Request,
    log_id: int = Path(..., ge=1),
):
    me = await _me(request)
    if not me:
        return _ensure_login(request, f"/invoice-exports?download_log_id={log_id}")

    acc = _get_access_token(request)

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=None) as client:
            r = await client.get(
                f"/api/v1/invoice-exports/logs/{log_id}/download",
                headers={"Authorization": f"Bearer {acc}"},
                follow_redirects=True,
            )

            # Nếu service A trả lỗi JSON/text -> forward luôn
            ct = (r.headers.get("content-type") or "").lower()
            if r.status_code != 200:
                if "application/json" in ct:
                    try:
                        return JSONResponse(status_code=r.status_code, content=r.json())
                    except Exception:
                        pass
                return JSONResponse(status_code=r.status_code, content={"error": r.text})

            # Stream bytes về browser
            cd = r.headers.get("content-disposition")

            # Ưu tiên tuyệt đối filename do Service A trả về
            if cd:
                content_disposition = cd
            else:
                # fallback hiếm khi dùng – vẫn KHÔNG hardcode chi tiết
                content_disposition = 'attachment; filename="invoice_export.xlsx"'

            return StreamingResponse(
                iter([r.content]),
                media_type=r.headers.get(
                    "content-type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                headers={"Content-Disposition": content_disposition},
            )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
