# routers/account.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx, os, re

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/account", tags=["account"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")

# =========================
# Helpers
# =========================
async def _me(request: Request) -> dict | None:
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    if not acc:
        return None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            r = await client.get("/auth/me", headers={"Authorization": f"Bearer {acc}"})
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

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

def _username_valid(u: str) -> bool:
    return re.fullmatch(r"[a-z0-9_]{3,32}", u) is not None

# =========================
# Views
# =========================
@router.get("", response_class=HTMLResponse)
async def account_home(request: Request):
    me = await _me(request)
    if not me:
        return RedirectResponse(url="/login?next=/account", status_code=303)

    role = (me.get("role") or "").upper()
    acc = request.cookies.get(ACCESS_COOKIE)

    profile = {
        "username": me.get("username"),
        "role": me.get("role"),
        "company_code": me.get("company_code"),
        "full_name": me.get("full_name", ""),
        "phone": me.get("phone", ""),
        "email": me.get("email", ""),
        "address": me.get("address", ""),
    }

    super_companies = None
    admin_users = None
    load_err = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            headers = {"Authorization": f"Bearer {acc}"}
            if role == "SUPER_ADMIN":
                st, data = await _get_json(client, "/api/v1/admin/companies", headers)
                if st == 200 and isinstance(data, dict):
                    super_companies = data.get("data", data)
                else:
                    load_err = f"Không tải được danh sách công ty (HTTP {st})."
            if role in ("SUPER_ADMIN", "COMPANY_ADMIN"):
                st, data = await _get_json(client, "/api/v1/admin/users", headers)
                if st == 200 and isinstance(data, dict):
                    admin_users = data.get("data", data)
                else:
                    load_err = f"Không tải được danh sách tài khoản (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/account/index.html",
        {
            "request": request,
            "me": me,
            "role": role,
            "profile": profile,
            "super_companies": super_companies,
            "admin_users": admin_users,
            "load_err": load_err,
        }
    )

# =========================
# Common actions
# =========================
@router.post("/change-password")
async def change_password(request: Request, old_password: str = Form(...), new_password: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, "/auth/change_password",
            {"Authorization": f"Bearer {acc}"},
            {"old_password": old_password, "new_password": new_password}
        )
    to = "/account?msg=changed" if st == 200 else "/account?err=change_failed"
    return RedirectResponse(url=to, status_code=303)

# =========================
# SUPER_ADMIN: Companies
# =========================
@router.post("/super/company/create")
async def super_company_create(request: Request, company_code: str = Form(...), name: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    payload = {"company_code": company_code.strip(), "name": name.strip()}

    if not re.fullmatch(r"[A-Za-z0-9_-]{2,40}", payload["company_code"]):
        return RedirectResponse(url="/account?err=bad_company_code", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(client, "/api/v1/admin/companies", {"Authorization": f"Bearer {acc}"}, payload)

    if st == 409:
        return RedirectResponse(url="/account?err=company_exists", status_code=303)
    to = "/account?msg=company_created" if st == 200 else "/account?err=create_company_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/super/company/enable")
async def super_company_enable(request: Request, company_code: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, f"/api/v1/admin/companies/{company_code}/enable",
            {"Authorization": f"Bearer {acc}"}, None
        )
    to = "/account?msg=company_enabled" if st == 200 else "/account?err=enable_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/super/company/disable")
async def super_company_disable(request: Request, company_code: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, f"/api/v1/admin/companies/{company_code}/disable",
            {"Authorization": f"Bearer {acc}"}, None
        )
    to = "/account?msg=company_disabled" if st == 200 else "/account?err=disable_failed"
    return RedirectResponse(url=to, status_code=303)

# =========================
# COMPANY_ADMIN: Users
# =========================
@router.post("/admin/user/create")
async def admin_user_create(request: Request, username: str = Form(...), password: str = Form(...), role: str = Form("STAFF")):
    acc = request.cookies.get(ACCESS_COOKIE)
    username = username.strip().lower()
    if not _username_valid(username):
        return RedirectResponse(url="/account?err=bad_username", status_code=303)

    payload = {"username": username, "password": password, "role": role}
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(client, "/api/v1/admin/users", {"Authorization": f"Bearer {acc}"}, payload)

    if st == 409:
        return RedirectResponse(url="/account?err=user_exists", status_code=303)
    to = "/account?msg=user_created" if st == 200 else "/account?err=create_user_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/admin/user/toggle")
async def admin_user_toggle(request: Request, user_id: int = Form(...), action: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    action = action.lower()
    if action not in ("enable", "disable"):
        return RedirectResponse(url="/account?err=bad_action", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, f"/api/v1/admin/users/{user_id}/{action}",
            {"Authorization": f"Bearer {acc}"}, None
        )
    to = "/account?msg=user_toggled" if st == 200 else "/account?err=user_toggle_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/admin/user/set-password")
async def admin_user_set_password(request: Request, user_id: int = Form(...), new_password: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, f"/api/v1/admin/users/{user_id}/force_set_password",
            {"Authorization": f"Bearer {acc}"}, {"new_password": new_password}
        )
    to = "/account?msg=pass_set" if st == 200 else "/account?err=set_pass_failed"
    return RedirectResponse(url=to, status_code=303)
