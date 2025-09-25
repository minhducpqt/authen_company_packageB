# routers/account.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, constr
import httpx, os, re

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/account", tags=["account"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")
REFRESH_COOKIE = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")

# =========================
# Helpers
# =========================
async def _me(request: Request) -> dict | None:
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)  # fallback
    if not acc:
        return None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            r = await client.get("/auth/me", headers={"Authorization": f"Bearer {acc}"})
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

async def _get_json(client: httpx.AsyncClient, url: str, headers: dict) -> tuple[int, dict | list | None]:
    r = await client.get(url, headers=headers)
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, data

async def _post_json(client: httpx.AsyncClient, url: str, headers: dict, payload: dict | None) -> tuple[int, dict | None]:
    r = await client.post(url, headers=headers, json=payload or {})
    try:
        data = r.json()
    except Exception:
        data = None
    return r.status_code, data

def _username_valid(u: str) -> bool:
    # Không dấu, không dấu chấm, chỉ a-z0-9_ và tối thiểu 3 ký tự
    return re.fullmatch(r"[a-z0-9_]{3,32}", u) is not None

# =========================
# Views
# =========================
@router.get("", response_class=HTMLResponse)
async def account_home(request: Request):
    me = await _me(request)
    if not me:
        # Middleware đã chặn, nhưng để phòng hờ:
        return RedirectResponse(url="/login?next=/account", status_code=303)

    role = (me.get("role") or "").upper()
    acc = request.cookies.get(ACCESS_COOKIE)

    # Common data
    profile = None
    profile_err = None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            # Thử lấy profile chi tiết; nếu API chưa có, fallback sang /auth/me
            st, data = await _get_json(client, "/api/v1/profile", {"Authorization": f"Bearer {acc}"})
            if st == 200 and isinstance(data, dict):
                profile = data
            else:
                profile = {
                    "username": me.get("username"),
                    "role": me.get("role"),
                    "company_code": me.get("company_code"),
                }
    except Exception as e:
        profile_err = str(e)

    # Role-specific data
    super_companies = None
    admin_users = None
    load_err = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            headers = {"Authorization": f"Bearer {acc}"}

            if role == "SUPER_ADMIN":
                # ➜ chỉnh lại URL nếu service A khác: /api/v1/super/companies
                st, data = await _get_json(client, "/api/v1/super/companies", headers)
                if st == 200:
                    super_companies = data.get("data", data)  # chấp nhận {data: [...]} hoặc [...]
                else:
                    load_err = f"Không tải được danh sách công ty (HTTP {st})."
            elif role == "COMPANY_ADMIN":
                # ➜ chỉnh lại URL nếu service A khác: /api/v1/admin/users
                st, data = await _get_json(client, "/api/v1/admin/users", headers)
                if st == 200:
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
            "profile_err": profile_err,
            "load_err": load_err,
            "super_companies": super_companies,
            "admin_users": admin_users,
        }
    )

# =========================
# Common actions
# =========================
@router.post("/change-password")
async def change_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
):
    acc = request.cookies.get(ACCESS_COOKIE)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(client, "/auth/change_password",
                                 {"Authorization": f"Bearer {acc}"},
                                 {"old_password": old_password, "new_password": new_password})
    # Quay lại trang account, đính kèm toast
    to = "/account?msg=changed" if st == 200 else "/account?err=change_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/profile/save")
async def profile_save(
    request: Request,
    full_name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
):
    acc = request.cookies.get(ACCESS_COOKIE)
    payload = {
        "full_name": full_name.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "address": address.strip(),
    }
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        # ➜ cần API profile tại Service A: POST /api/v1/profile
        st, _ = await _post_json(client, "/api/v1/profile", {"Authorization": f"Bearer {acc}"}, payload)
    to = "/account?msg=profile_saved" if st == 200 else "/account?err=profile_failed"
    return RedirectResponse(url=to, status_code=303)

# =========================
# SUPER_ADMIN: Companies
# =========================
@router.post("/super/company/toggle")
async def super_company_toggle(request: Request, company_id: int = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        # ➜ chỉnh URL nếu khác: POST /api/v1/super/companies/toggle
        st, _ = await _post_json(client, "/api/v1/super/companies/toggle",
                                 {"Authorization": f"Bearer {acc}"},
                                 {"company_id": company_id})
    to = "/account?msg=company_toggled" if st == 200 else "/account?err=toggle_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/super/company/create")
async def super_company_create(request: Request, company_code: str = Form(...), name: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    company_code = company_code.strip()
    name = name.strip()

    if not re.fullmatch(r"[A-Za-z0-9_-]{2,40}", company_code):
        return RedirectResponse(url="/account?err=bad_company_code", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        # ➜ chỉnh URL nếu khác: POST /api/v1/super/companies
        st, data = await _post_json(client, "/api/v1/super/companies",
                                    {"Authorization": f"Bearer {acc}"},
                                    {"company_code": company_code, "name": name})
    if st == 409:
        return RedirectResponse(url="/account?err=company_exists", status_code=303)
    to = "/account?msg=company_created" if st == 200 else "/account?err=create_company_failed"
    return RedirectResponse(url=to, status_code=303)

# =========================
# COMPANY_ADMIN: Users
# =========================
@router.post("/admin/user/toggle")
async def admin_user_toggle(request: Request, user_id: int = Form(...), action: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    action = action.lower()
    if action not in ("enable", "disable"):
        return RedirectResponse(url="/account?err=bad_action", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(client, f"/api/v1/admin/users/{user_id}/{action}",
                                 {"Authorization": f"Bearer {acc}"}, None)
    to = "/account?msg=user_toggled" if st == 200 else "/account?err=user_toggle_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/admin/user/create")
async def admin_user_create(request: Request, username: str = Form(...), password: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    username = username.strip().lower()

    if not _username_valid(username):
        return RedirectResponse(url="/account?err=bad_username", status_code=303)

    # Role mặc định cho tài khoản con là "STAFF" (bạn có thể đổi)
    payload = {
        "username": username,
        "password": password,
        "role": "STAFF",         # ➜ chỉnh nếu cần
        # company_code sẽ do Service A gán theo admin hiện tại hoặc truyền vào payload nếu API yêu cầu
    }
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(client, "/api/v1/admin/users",
                                 {"Authorization": f"Bearer {acc}"}, payload)
    to = "/account?msg=user_created" if st == 200 else "/account?err=create_user_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/admin/user/set-password")
async def admin_user_set_password(request: Request, user_id: int = Form(...), new_password: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(client, f"/auth/set_password/{user_id}",
                                 {"Authorization": f"Bearer {acc}"},
                                 {"new_password": new_password})
    to = "/account?msg=pass_set" if st == 200 else "/account?err=set_pass_failed"
    return RedirectResponse(url=to, status_code=303)
