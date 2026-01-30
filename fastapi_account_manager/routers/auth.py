# fastapi_account_manager/routers/auth.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx
import os
from urllib.parse import urlparse
from utils.templates import templates

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


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, next: str | None = "/"):
    return templates.TemplateResponse(
        "pages/authen/login.html",
        {"request": request, "next": next or "/"}
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/")
):
    # 1) Gọi Service A /auth/login
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        r = await client.post("/auth/login", json={"username": username, "password": password})

    if r.status_code != 200:
        return templates.TemplateResponse(
            "pages/authen/login.html",
            {"request": request, "next": next or "/", "error": "Sai tài khoản hoặc mật khẩu"},
            status_code=401
        )

    # 2) Lấy token
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    access = data.get("access_token")
    refresh = data.get("refresh_token")

    # 3) Safe next (logic cũ)
    safe_next = _safe_next(next or "/")

    # 4) Best-effort fetch role
    role = None
    try:
        role = await _best_effort_fetch_role(access)
    except Exception:
        role = None

    role_u = (role or "").upper().strip()

    # ✅ RULE MỚI:
    # - Nếu COMPANY_ADMIN: GIỮ redirect như cũ (tôn trọng next)
    # - Nếu KHÔNG phải admin: ÉP về menu item đầu tiên của role (bỏ qua next)
    if role_u != "COMPANY_ADMIN":
        safe_next = _first_menu_for_non_admin(role_u)

    # 5) RedirectResponse + set cookies
    resp = RedirectResponse(url=safe_next, status_code=303)

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

    # role cookie: xoá trước để tránh dính role cũ
    resp.delete_cookie(ROLE_COOKIE_NAME, path="/")
    if role_u:
        resp.set_cookie(
            key=ROLE_COOKIE_NAME, value=role_u, httponly=True,
            secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/"
        )

    return resp


@router.get("/logout")
async def logout(request: Request):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    resp.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    resp.delete_cookie(ROLE_COOKIE_NAME, path="/")

    # Gọi Service A /auth/logout (best-effort)
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


# ✅ UI base.html đang POST /account/logout & /account/logout_all
@router.post("/account/logout")
async def account_logout(request: Request):
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    resp.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    resp.delete_cookie(ROLE_COOKIE_NAME, path="/")

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
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    resp.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    resp.delete_cookie(ROLE_COOKIE_NAME, path="/")

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
