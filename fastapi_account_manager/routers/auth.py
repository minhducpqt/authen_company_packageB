# fastapi_account_manager/routers/auth.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx
import os
from urllib.parse import urlparse
from utils.templates import templates

router = APIRouter(tags=["auth"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")
ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")

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

    # 3) Chuẩn hoá next: chỉ cho relative path + giữ nguyên query
    try:
        p = urlparse(next or "/")
        safe_next = (p.path or "/") + (f"?{p.query}" if p.query else "")
    except Exception:
        safe_next = "/"

    if safe_next.startswith("/login") or not safe_next.strip():
        safe_next = "/"

    # 4) Tạo RedirectResponse và gắn cookie lên chính response này
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
    return resp

@router.get("/logout")
async def logout(request: Request):
    # Xoá cookie phía Dashboard bằng cách set quá khứ
    resp = RedirectResponse(url="/login", status_code=303)
    resp.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    resp.delete_cookie(REFRESH_COOKIE_NAME, path="/")

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
