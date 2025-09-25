# fastapi_account_manager/routers/auth.py
from fastapi import APIRouter, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Depends
import httpx
import os
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
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/")
):
    # Gọi Service A /auth/login
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
        r = await client.post("/auth/login", json={"username": username, "password": password})

    if r.status_code != 200:
        # render lại form với lỗi
        return templates.TemplateResponse(
            "pages/authen/login.html",
            {"request": request, "next": next, "error": "Sai tài khoản hoặc mật khẩu"},
            status_code=401
        )

    data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
    access = data.get("access_token")
    refresh = data.get("refresh_token")

    # Set cookie tại Dashboard (cookie theo host, không theo port)
    if access:
        response.set_cookie(
            key=ACCESS_COOKIE_NAME, value=access, httponly=True,
            secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/"
        )
    if refresh:
        response.set_cookie(
            key=REFRESH_COOKIE_NAME, value=refresh, httponly=True,
            secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, path="/"
        )

    # Redirect về trang mong muốn
    return RedirectResponse(url=next or "/", status_code=303)

@router.get("/logout")
async def logout(request: Request, response: Response):
    # Đọc cookie hiện có
    acc = request.cookies.get(ACCESS_COOKIE_NAME)
    rt = request.cookies.get(REFRESH_COOKIE_NAME)

    # Gọi Service A /auth/logout (không bắt buộc thành công)
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=5.0) as client:
            await client.post(
                "/auth/logout",
                headers={"Authorization": f"Bearer {acc}"} if acc else {},
                json={"refresh_token": rt} if rt else None
            )
    except Exception:
        pass

    # Xoá cookie phía Dashboard
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/")

    return RedirectResponse(url="/login", status_code=303)
