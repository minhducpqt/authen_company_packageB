# routers/account.py
from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx, os, re
from urllib.parse import quote

from fastapi_account_manager.middlewares.auth_guard import ACCESS_COOKIE_NAME
from utils.templates import templates

router = APIRouter(prefix="/account", tags=["account"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")

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
    return re.fullmatch(r"[a-z0-9_]{3,32}", u or "") is not None

@router.get("", response_class=HTMLResponse)
async def account_home(request: Request):
    me = await _me(request)
    if not me:
        return RedirectResponse(url="/login?next=/account", status_code=303)

    role = (me.get("role") or "").upper()
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)

    profile = {
        "username": me.get("username"),
        "role": me.get("role"),
        "company_code": me.get("company_code"),
    }

    super_companies = None
    admin_users = None
    load_err = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            headers = {"Authorization": f"Bearer {acc}"}

            if role == "SUPER_ADMIN":
                # size <= 200 để không bị 422
                st, data = await _get_json(client, "/api/v1/admin/companies?page=1&size=200", headers)
                if st == 200 and isinstance(data, dict):
                    super_companies = data.get("data", data)
                else:
                    load_err = f"Không tải được danh sách công ty (HTTP {st})."

            elif role == "COMPANY_ADMIN":
                st, data = await _get_json(client, "/api/v1/admin/users?page=1&size=50", headers)
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

@router.get("/company/{company_code}", response_class=HTMLResponse)
async def company_detail(request: Request, company_code: str):
    me = await _me(request)
    if not me:
        return RedirectResponse(url=f"/login?next=/account/company/{quote(company_code)}", status_code=303)

    role = (me.get("role") or "").upper()
    if role != "SUPER_ADMIN":
        return RedirectResponse(url="/account?err=forbidden", status_code=303)

    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    load_err = None
    company = None
    users = None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            headers = {"Authorization": f"Bearer {acc}"}

            # lấy thông tin công ty (size <= 200)
            st, data = await _get_json(client, "/api/v1/admin/companies?page=1&size=200", headers)
            if st == 200 and isinstance(data, dict):
                arr = data.get("data", [])
                company = next((c for c in arr if (c.get("company_code") or "").lower() == company_code.lower()), None)

            # lấy user theo company_code (API đã được sửa để hỗ trợ filter)
            st, data = await _get_json(client, f"/api/v1/admin/users?company_code={quote(company_code)}&page=1&size=100", headers)
            if st == 200 and isinstance(data, dict):
                users = data.get("data", data)
            else:
                load_err = f"Không tải được danh sách user của {company_code} (HTTP {st})."
    except Exception as e:
        load_err = str(e)

    return templates.TemplateResponse(
        "pages/account/company_detail.html",
        {
            "request": request,
            "role": role,
            "company_code": company_code,
            "company": company,
            "users": users,
            "load_err": load_err,
        }
    )

@router.post("/change-password")
async def change_password(request: Request, old_password: str = Form(...), new_password: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, "/auth/change_password",
            {"Authorization": f"Bearer {acc}"},
            {"old_password": old_password, "new_password": new_password}
        )
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
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    payload = {
        "full_name": full_name.strip(),
        "phone": phone.strip(),
        "email": email.strip(),
        "address": address.strip(),
    }
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(client, "/api/v1/profile", {"Authorization": f"Bearer {acc}"}, payload)
    to = "/account?msg=profile_saved" if st == 200 else "/account?err=profile_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/super/company/create")
async def super_company_create(request: Request, company_code: str = Form(...), name: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    company_code = (company_code or "").strip()
    name = (name or "").strip()

    if not re.fullmatch(r"[A-Za-z0-9_-]{2,40}", company_code):
        return RedirectResponse(url="/account?err=bad_company_code", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, "/api/v1/admin/companies",
            {"Authorization": f"Bearer {acc}"},
            {"company_code": company_code, "name": name}
        )
    if st == 409:
        return RedirectResponse(url="/account?err=company_exists", status_code=303)
    to = "/account?msg=company_created" if st == 200 else "/account?err=create_company_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/super/company/enable")
async def super_company_enable(request: Request, company_code: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, f"/api/v1/admin/companies/{company_code}/enable",
            {"Authorization": f"Bearer {acc}"}, None
        )
    to = "/account?msg=company_enabled" if st == 200 else "/account?err=enable_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/super/company/disable")
async def super_company_disable(request: Request, company_code: str = Form(...)):
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, f"/api/v1/admin/companies/{company_code}/disable",
            {"Authorization": f"Bearer {acc}"}, None
        )
    to = "/account?msg=company_disabled" if st == 200 else "/account?err=disable_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/admin/user/create")
async def admin_user_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form("STAFF"),
    company_code: str | None = Form(None),
    next: str | None = Form(None),
):
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    username = (username or "").strip().lower()
    if not _username_valid(username):
        redir = next or "/account"
        return RedirectResponse(url=f"{redir}?err=bad_username", status_code=303)

    payload = {"username": username, "password": password, "role": role}
    if company_code:
        payload["company_code"] = company_code

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(client, "/api/v1/admin/users", {"Authorization": f"Bearer {acc}"}, payload)

    if st == 409:
        redir = next or "/account"
        return RedirectResponse(url=f"{redir}?err=user_exists", status_code=303)

    redir = next or "/account"
    to = f"{redir}?msg=user_created" if st == 200 else f"{redir}?err=create_user_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/admin/user/toggle")
async def admin_user_toggle(
    request: Request,
    user_id: int = Form(...),
    action: str = Form(...),
    next: str | None = Form(None),
):
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    action = (action or "").lower()
    if action not in ("enable", "disable"):
        redir = next or "/account"
        return RedirectResponse(url=f"{redir}?err=bad_action", status_code=303)

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, f"/api/v1/admin/users/{user_id}/{action}",
            {"Authorization": f"Bearer {acc}"}, None
        )
    redir = next or "/account"
    to = f"{redir}?msg=user_toggled" if st == 200 else f"{redir}?err=user_toggle_failed"
    return RedirectResponse(url=to, status_code=303)

@router.post("/admin/user/set-password")
async def admin_user_set_password(
    request: Request,
    user_id: int = Form(...),
    new_password: str = Form(...),
    next: str | None = Form(None),
):
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        st, _ = await _post_json(
            client, f"/api/v1/admin/users/{user_id}/force_set_password",
            {"Authorization": f"Bearer {acc}"},
            {"new_password": new_password}
        )
    redir = next or "/account"
    to = f"{redir}?msg=pass_set" if st == 200 else f"{redir}?err=set_pass_failed"
    return RedirectResponse(url=to, status_code=303)

def _clear_auth_cookies(resp: RedirectResponse):
    resp.delete_cookie(ACCESS_COOKIE, path="/")
    resp.delete_cookie("refresh_token", path="/")  # hoặc lấy REFRESH_COOKIE từ env nếu có
    if ACCESS_COOKIE_NAME != ACCESS_COOKIE:
        resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    return resp

@router.get("/change-password-form", response_class=HTMLResponse)
async def change_password_form(request: Request):
    return templates.TemplateResponse(
        "pages/account/change_password.html",
        {"request": request, "title": "Đổi mật khẩu"}
    )
@router.post("/logout")
async def logout(request: Request):
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            if acc:
                await client.post("/auth/logout", headers={"Authorization": f"Bearer {acc}"})
    except Exception:
        pass
    resp = RedirectResponse(url="/login", status_code=303)
    return _clear_auth_cookies(resp)

@router.post("/logout_all")
async def logout_all(request: Request):
    acc = request.cookies.get(ACCESS_COOKIE) or request.cookies.get(ACCESS_COOKIE_NAME)
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            if acc:
                await client.post("/auth/logout_all", headers={"Authorization": f"Bearer {acc}"})
    except Exception:
        pass
    resp = RedirectResponse(url="/login", status_code=303)
    return _clear_auth_cookies(resp)