# fastapi_account_manager/routers/auth.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx
import os
from urllib.parse import urlparse
from utils.templates import templates
from utils.device_cookie import (
    clear_device_cookies_for_user,
    forward_device_cookies,
    set_device_cookie_for_user,
)
from utils.auth import set_ui_profile_cookies, clear_ui_profile_cookies

router = APIRouter(tags=["auth"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
ROLE_COOKIE_NAME = os.getenv("ROLE_COOKIE_NAME", "user_role")

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")


async def _best_effort_fetch_role(access_token: str | None) -> str | None:
    """Best-effort lấy role từ Service A để set cookie user_role. Fail thì None."""
    if not access_token:
        return None

    headers = {"Authorization": f"Bearer {access_token}"}
    candidates = ["/me/profile", "/me", "/auth/me", "/account/me", "/users/me"]

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=6.0) as client:
            for path in candidates:
                try:
                    r = await client.get(path, headers=headers)
                    if r.status_code != 200:
                        continue
                    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                    role = (
                        data.get("role")
                        or data.get("user_role")
                        or (data.get("user") or {}).get("role")
                        or (data.get("profile") or {}).get("role")
                    )
                    if role:
                        return str(role).upper().strip()
                except Exception:
                    continue
    except Exception:
        return None

    return None


def _safe_next(next_url: str | None) -> str:
    """Chuẩn hoá next: chỉ cho relative path + giữ nguyên query."""
    try:
        p = urlparse(next_url or "/")
        safe = (p.path or "/") + (f"?{p.query}" if p.query else "")
    except Exception:
        safe = "/"

    if safe.startswith("/login") or not safe.strip():
        safe = "/"
    return safe


def _first_menu_for_non_admin(role: str | None) -> str:
    """
    Menu item đầu tiên cho các role KHÔNG phải admin theo quy ước bạn chốt:
      - STAFF / VIEWER / ACCOUNTANT => 2.1 Mua hồ sơ
      - fallback => 2.1
    """
    r = (role or "").upper().strip()
    if r in ["STAFF", "VIEWER", "ACCOUNTANT"]:
        return "/transactions/dossiers"
    return "/transactions/dossiers"


def _set_auth_cookies(resp: RedirectResponse, access: str | None, refresh: str | None, role: str | None):
    if access:
        resp.set_cookie(
            key=ACCESS_COOKIE_NAME, value=access, httponly=True,
            secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/"
        )
    if refresh:
        resp.set_cookie(
            key=REFRESH_COOKIE_NAME, value=refresh, httponly=True,
            secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/"
        )
    resp.delete_cookie(ROLE_COOKIE_NAME, path="/")
    if role:
        resp.set_cookie(
            key=ROLE_COOKIE_NAME, value=role, httponly=True,
            secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/"
        )


def _set_device_cookie(resp: RedirectResponse, username: str, device_id: str | None):
    set_device_cookie_for_user(resp, username, device_id)


async def _current_username(request: Request) -> str | None:
    acc = request.cookies.get(ACCESS_COOKIE_NAME)
    if not acc:
        return None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=6.0) as client:
            r = await client.get("/auth/me", headers={"Authorization": f"Bearer {acc}"})
        if r.status_code != 200:
            return None
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        u = (data.get("username") or "").strip()
        return u or None
    except Exception:
        return None


async def _finalize_login(request: Request, data: dict, safe_next: str, username: str):
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    role = None
    try:
        role = await _best_effort_fetch_role(access)
    except Exception:
        role = None
    role_u = (role or data.get("role") or "").upper().strip()
    if role_u != "COMPANY_ADMIN":
        safe_next = _first_menu_for_non_admin(role_u)
    resp = RedirectResponse(url=safe_next, status_code=303)
    _set_auth_cookies(resp, access, refresh, role_u)
    _set_device_cookie(resp, username, data.get("device_id"))
    # Cookie hiển thị menu (không liên quan RBAC / auth)
    set_ui_profile_cookies(
        resp,
        username=username,
        company_code=data.get("company_code"),
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )
    return resp


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, next: str | None = "/"):
    return templates.TemplateResponse(
        "pages/authen/login.html",
        {"request": request, "next": next or "/"}
    )


@router.get("/login/otp", response_class=HTMLResponse)
async def login_otp_form(
    request: Request,
    challenge_id: str,
    next: str | None = "/",
    purpose_label: str | None = None,
    username: str | None = None,
):
    return templates.TemplateResponse(
        "pages/authen/login_otp.html",
        {
            "request": request,
            "challenge_id": challenge_id,
            "next": next or "/",
            "purpose_label": purpose_label or "Xác thực OTP",
            "username": (username or "").strip(),
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/")
):
    safe_next = _safe_next(next or "/")
    username_clean = (username or "").strip()
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
        r = await client.post(
            "/auth/web/login",
            json={"username": username, "password": password},
            cookies=forward_device_cookies(request, username_clean),
        )

    if r.status_code == 401:
        return templates.TemplateResponse(
            "pages/authen/login.html",
            {"request": request, "next": safe_next, "error": "Sai tài khoản hoặc mật khẩu"},
            status_code=401,
        )
    if r.status_code >= 400:
        detail = "Đăng nhập thất bại"
        try:
            body = r.json()
            if isinstance(body, dict):
                detail = body.get("detail") if isinstance(body.get("detail"), str) else detail
        except Exception:
            pass
        return templates.TemplateResponse(
            "pages/authen/login.html",
            {"request": request, "next": safe_next, "error": detail},
            status_code=r.status_code,
        )

    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}

    if data.get("otp_required"):
        from urllib.parse import urlencode
        q = urlencode({
            "challenge_id": data.get("challenge_id"),
            "next": safe_next,
            "purpose_label": data.get("purpose_label") or "",
            "username": username_clean,
        })
        return RedirectResponse(url=f"/login/otp?{q}", status_code=303)

    return await _finalize_login(request, data, safe_next, username_clean)


@router.post("/login/otp")
async def login_otp_submit(
    request: Request,
    challenge_id: str = Form(...),
    otp_code: str = Form(...),
    next: str = Form("/"),
    username: str = Form(""),
    trust_device: str | None = Form(None),
):
    safe_next = _safe_next(next or "/")
    username_clean = (username or "").strip()
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
        r = await client.post(
            "/auth/web/otp/verify",
            json={
                "challenge_id": challenge_id,
                "otp_code": otp_code.strip(),
                "trust_device": trust_device == "1",
            },
            cookies=forward_device_cookies(request, username_clean),
        )

    if r.status_code >= 400:
        err = "Mã OTP không đúng hoặc đã hết hạn"
        try:
            body = r.json()
            d = body.get("detail")
            if isinstance(d, dict):
                code = d.get("error")
                if code == "EXPIRED":
                    err = "Mã OTP đã hết hạn. Vui lòng đăng nhập lại."
                elif code == "INVALID_OTP":
                    left = d.get("attempts_left")
                    err = "Mã OTP không đúng" + (f" (còn {left} lần)" if left is not None else "")
                elif code in ("CHALLENGE_NOT_FOUND", "CANCELLED"):
                    err = "Phiên OTP không còn hiệu lực. Vui lòng đăng nhập lại."
                elif code == "LOCKED":
                    err = "Đã nhập sai quá số lần cho phép. Vui lòng đăng nhập lại."
        except Exception:
            pass
        return templates.TemplateResponse(
            "pages/authen/login_otp.html",
            {
                "request": request,
                "challenge_id": challenge_id,
                "next": safe_next,
                "purpose_label": "Xác thực OTP",
                "username": username_clean,
                "error": err,
            },
            status_code=400,
        )

    data = r.json()
    return await _finalize_login(request, data, safe_next, username_clean)


@router.post("/login/otp/resend")
async def login_otp_resend(
    request: Request,
    challenge_id: str = Form(...),
    next: str = Form("/"),
    purpose_label: str = Form("Xác thực OTP"),
    username: str = Form(""),
):
    safe_next = _safe_next(next or "/")
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
        r = await client.post(
            "/auth/web/otp/resend",
            json={"challenge_id": challenge_id},
        )
    msg = None
    err = None
    new_challenge_id = challenge_id
    if r.status_code == 200:
        body = r.json()
        new_challenge_id = body.get("challenge_id") or challenge_id
        msg = "Đã gửi lại mã OTP qua Telegram."
    else:
        err = "Không thể gửi lại OTP. Thử đăng nhập lại."
    return templates.TemplateResponse(
        "pages/authen/login_otp.html",
        {
            "request": request,
            "challenge_id": new_challenge_id,
            "next": safe_next,
            "purpose_label": purpose_label,
            "username": (username or "").strip(),
            "msg": msg,
            "error": err,
        },
    )


@router.get("/logout")
async def logout(request: Request):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    resp.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    resp.delete_cookie(ROLE_COOKIE_NAME, path="/")
    clear_ui_profile_cookies(resp, path="/")

    try:
        acc = request.cookies.get(ACCESS_COOKIE_NAME)
        rt = request.cookies.get(REFRESH_COOKIE_NAME)
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=5.0) as client:
            await client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {acc}"} if acc else {},
                json={"refresh_token": rt} if rt else None,
            )
    except Exception:
        pass

    return resp


@router.post("/account/logout")
async def account_logout(request: Request):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    resp.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    resp.delete_cookie(ROLE_COOKIE_NAME, path="/")
    clear_ui_profile_cookies(resp, path="/")

    try:
        acc = request.cookies.get(ACCESS_COOKIE_NAME)
        rt = request.cookies.get(REFRESH_COOKIE_NAME)
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=5.0) as client:
            await client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {acc}"} if acc else {},
                json={"refresh_token": rt} if rt else None,
            )
    except Exception:
        pass

    return resp


@router.post("/account/logout_all")
async def account_logout_all(request: Request):
    username = await _current_username(request)
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    resp.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    resp.delete_cookie(ROLE_COOKIE_NAME, path="/")
    clear_ui_profile_cookies(resp, path="/")
    clear_device_cookies_for_user(resp, username)

    try:
        acc = request.cookies.get(ACCESS_COOKIE_NAME)
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=6.0) as client:
            r = await client.post(
                "/auth/logout_all",
                headers={"Authorization": f"Bearer {acc}"} if acc else {},
            )
            if r.status_code >= 400:
                await client.post(
                    "/auth/logout",
                    headers={"Authorization": f"Bearer {acc}"} if acc else {},
                    json=None,
                )
    except Exception:
        pass

    return resp
