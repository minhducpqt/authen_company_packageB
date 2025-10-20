# main.py
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

# Middleware xác thực
from fastapi_account_manager.middlewares.auth_guard import auth_guard_middleware

# Routers
from fastapi_account_manager.routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.account import router as account_router
from routers.projects import router as projects_router
from routers.project_payment_accounts import router as ppa_router
from routers.customers import router as customers_router
from routers.settings.settings_bank_accounts import router as settings_bank_accounts_router
from routers.settings.settings_company import router as settings_company_router
from routers import bank_transactions
from routers.bank_import.router import router as bank_import_router
from routers.send_info_dossier import router as send_info_dossier_router


def _dump_bank_routes(app: FastAPI) -> None:
    print("=== ROUTE DUMP (bank) ===")
    for r in app.routes:
        p = getattr(r, "path", "")
        name = getattr(r, "name", "")
        if p.startswith("/giao-dich-ngan-hang"):
            print(
                f"[ROUTE] path={p} name={name} "
                f"methods={getattr(r, 'methods', None)} "
                f"endpoint={getattr(r, 'endpoint', None)}"
            )
    print("=========================")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # --- startup ---
    _dump_bank_routes(app)
    yield
    # --- shutdown ---
    # (nếu cần đóng kết nối/cleanup thì thêm ở đây)


app = FastAPI(title="Dashboard Công ty — v20", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.middleware("http")(auth_guard_middleware)

# Đăng ký routers
app.include_router(ppa_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(account_router)
app.include_router(projects_router)
app.include_router(settings_bank_accounts_router)
app.include_router(settings_company_router)
app.include_router(customers_router)
app.include_router(bank_transactions.router)
app.include_router(bank_import_router)
app.include_router(send_info_dossier_router)


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/tien-ich-khac")
def _legacy_tools_redirect():
    return RedirectResponse(url="/account", status_code=303)


@app.get("/quan-ly-tai-khoan")
def _legacy_account_redirect():
    return RedirectResponse(url="/account", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8887, reload=True)
