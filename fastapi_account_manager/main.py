from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import RedirectResponse

from pathlib import Path
import os

from fastapi_authen import auth_router, current_user, User
from .middlewares.auth_middleware import AuthMiddleware
from .routers.accounts import router as accounts_router
from .routers.admin import router as admin_router
from .routers.super import router as super_router

# ----- Config riêng cho Module B (đọc từ ENV) -----
AM_LOGIN_REDIRECT_URL = os.getenv("AM_LOGIN_REDIRECT_URL", "/accounts/dashboard")

# ----- Đường dẫn tài nguyên trong package (an toàn khi cài dạng wheel) -----
PKG_ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = str(PKG_ROOT / "templates")
STATIC_DIR = str(PKG_ROOT / "static")


def create_app() -> FastAPI:
    app = FastAPI(title="FastAPI Account Manager")

    # Static & templates
    app.mount("/accounts/static", StaticFiles(directory=STATIC_DIR), name="am_static")
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # Middleware: auto refresh & login redirect
    app.add_middleware(AuthMiddleware)

    # Auth endpoints từ Module A (giữ nguyên prefix /auth như đã include ở app ngoài nếu cần)
    app.include_router(auth_router, prefix="")

    # Module B routers
    app.include_router(accounts_router, prefix="/accounts")
    app.include_router(admin_router, prefix="/accounts")
    app.include_router(super_router, prefix="/accounts")

    # Entry: /accounts -> redirect về dashboard (hoặc URL cấu hình)
    @app.get("/accounts")
    def accounts_index(request: Request, user: User = Depends(current_user)):
        return RedirectResponse(AM_LOGIN_REDIRECT_URL, status_code=303)

    # Dashboard tối giản
    @app.get("/accounts/dashboard")
    def dashboard(request: Request, user: User = Depends(current_user)):
        return templates.TemplateResponse("dashboard.html", {"request": request, "me": user})

    return app
