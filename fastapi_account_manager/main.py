from fastapi import FastAPI, Request, Depends, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse, HTMLResponse
from pathlib import Path
import httpx, os

from fastapi_authen import current_user, User  # ❌ Đừng import auth_router ở đây
from .middlewares.auth_middleware import AuthMiddleware
from .routers.accounts import router as accounts_router
from .routers.admin import router as admin_router
from .routers.super import router as super_router

AM_LOGIN_REDIRECT_URL = os.getenv("AM_LOGIN_REDIRECT_URL", "/accounts/dashboard")

PKG_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = str(PKG_ROOT / "templates")
STATIC_DIR = str(PKG_ROOT / "static")

def create_app() -> FastAPI:
    app = FastAPI(title="FastAPI Account Manager")

    # static & templates (⚠️ mount relative, sub-app sẽ thành /accounts/static)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="am_static")
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # middleware
    app.add_middleware(AuthMiddleware)

    # ⛔️ KHÔNG include auth_router trong B (auth ở root app)
    # app.include_router(auth_router)

    # include các router của B (relative)
    app.include_router(accounts_router)  # routes bắt đầu bằng /users, /users/{id}...
    app.include_router(admin_router)     # /admin
    app.include_router(super_router)     # /super

    # ---------- LOGIN UI (relative paths) ----------
    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        return templates.TemplateResponse("login.html", {"request": request})

    @app.post("/login")
    async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
        # Gọi API /auth/login ở ROOT (app chính)
        async with httpx.AsyncClient(base_url=str(request.base_url)) as client:
            r = await client.post("/auth/login", json={"username": username, "password": password})

        if r.status_code != 200:
            return templates.TemplateResponse(
                "login.html", {"request": request, "error": "Sai thông tin đăng nhập"}, status_code=401
            )

        resp = RedirectResponse(AM_LOGIN_REDIRECT_URL, status_code=303)

        # copy Set-Cookie từ Module A
        set_cookie_headers = r.headers.get_all("set-cookie") if hasattr(r.headers, "get_all") else r.headers.get("set-cookie", "").split(", ") if r.headers.get("set-cookie") else []
        from http.cookies import SimpleCookie
        for cstr in set_cookie_headers:
            if not cstr:
                continue
            jar = SimpleCookie(); jar.load(cstr)
            for name, morsel in jar.items():
                params = {k.lower(): morsel[k] for k in morsel.keys() if morsel[k]}
                max_age = int(params.get("max-age")) if "max-age" in params else None
                samesite = params.get("samesite") or "Lax"
                secure = ("secure" in params) or False
                path = params.get("path") or "/"
                resp.set_cookie(
                    key=name, value=morsel.value,
                    httponly=True, secure=secure, samesite=samesite, max_age=max_age, path=path
                )
        return resp
    # ----------------------------------------------

    # Entry của sub-app (→ /accounts trên app chính)
    @app.get("/")
    def accounts_index(request: Request, user: User = Depends(current_user)):
        return RedirectResponse(AM_LOGIN_REDIRECT_URL, status_code=303)

    @app.get("/dashboard")
    def dashboard(request: Request, user: User = Depends(current_user)):
        return templates.TemplateResponse("dashboard.html", {"request": request, "me": user})

    return app
