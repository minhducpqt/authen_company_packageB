# fastapi_account_manager/routers/projects_io.py  (WEB)
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse
import os

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.excel_templates import build_projects_lots_template
from utils.excel_import import handle_import_projects, apply_import_projects

router = APIRouter(prefix="/projects-io", tags=["projects-io"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token") or ACCESS_COOKIE_NAME

def _get_access(request: Request) -> str | None:
    return request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)

@router.get("/template")
async def download_template():
    # Trả file Excel template (StreamingResponse)
    return build_projects_lots_template()

@router.post("/import/preview")
async def import_preview(request: Request, file: UploadFile = File(...)):
    access = _get_access(request)
    if not access:
        return RedirectResponse("/login?next=/projects", status_code=303)

    try:
        preview = await handle_import_projects(file, access)
        # Lưu tạm vào session-like store đơn giản (cookie, query, hoặc cache).
        # Ở đây chuyển nhanh qua query bằng cách cất vào signed cookie?
        # Để đơn giản: serialize và nhét vào cookie tạm (<= 4KB). Nếu dữ liệu lớn, đưa vào server cache.
        from fastapi.responses import JSONResponse
        resp = JSONResponse({"ok": True, "preview": preview})
        return resp
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)

@router.post("/import/apply")
async def import_apply(
    request: Request,
    # frontend sẽ gửi lại payload (json) đã nhận ở preview để đảm bảo đồng nhất
    # nếu bạn muốn forward thẳng file -> preview -> apply trong 1 request thì có thể thay đổi luồng
    payload_json: str = Form(...),
    company_code: str = Form(...),
    force_replace: bool = Form(False),
):
    access = _get_access(request)
    if not access:
        return RedirectResponse("/login?next=/projects", status_code=303)

    import json
    try:
        payload = json.loads(payload_json or "{}")
        result = apply_import_projects(payload, access, company_code=company_code, force_replace=force_replace)
        code = result.get("code", 500)
        from fastapi.responses import JSONResponse
        return JSONResponse(result, status_code=code if code else 200)
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse({"code": 400, "message": str(e)}, status_code=400)
