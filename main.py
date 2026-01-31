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
from routers.account import router as account_router
from routers.projects import router as projects_router
from routers.project_payment_accounts import router as ppa_router
from routers.customers import router as customers_router
from routers.settings.settings_bank_accounts import router as settings_bank_accounts_router
from routers.settings.settings_company import router as settings_company_router
from routers import bank_transactions
from routers.bank_import.router import router as bank_import_router
from routers.send_info_dossier import router as send_info_dossier_router
from routers.dossier_buyers import router as dossier_buyers_router
from routers import transactions  # <-- NEW
from routers.api_proxy import router as api_proxy_router  # <-- NEW
from routers.reports import router as reports_router
from routers.reports_export import router as reports_export_router
from routers.dashboard import router as dashboard_router
from routers import company_mailers
from routers import auction_docs  # import file mới
from routers import bid_tickets as bid_tickets_router
from routers.auction_counting import router as auction_counting_router
from routers.auction_sessions import router as auction_sessions_router
from routers.auction_session_bid_sheets import router as auction_session_bid_sheets_router
from routers.auction_session_winner_prints import router as auction_session_winner_prints_router
from routers.auction_documents_print import router as auction_documents_print_router
from fastapi_account_manager.middlewares.rbac_guard import rbac_guard_middleware

# ✅ Lots (tách từ projects.py)
from routers.lots import router as lots_router  # <-- NEW

# Bid attendance
from routers import bid_attendance as bid_attendance_router
from routers.bid_attendance_exclusions import router as bid_attendance_exclusions_router

from routers.customer_documents import router as customer_documents_router
from routers.announcements import router as announcements_router
from routers.auction_results import router as auction_results_router
from routers import deposit_refunds
from routers.auction_prints import router as auction_prints_router
from routers import auction_session_display

#Mobile
from routers.mobile.wire import mount_routers as mount_mobile_routers


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


app = FastAPI(
    title="Dashboard Công ty — v20",
    lifespan=lifespan,
    docs_url=None,  # TẮT /docs
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.middleware("http")(auth_guard_middleware)

app.middleware("http")(rbac_guard_middleware)  # ✅ chạy sau auth_guard


# Đăng ký routers
app.include_router(api_proxy_router)  # <-- NEW: /api/*
app.include_router(ppa_router)
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(account_router)
app.include_router(projects_router)

# ✅ lots router (đặt gần projects để dễ quản lý)
app.include_router(lots_router)  # <-- NEW: /lots/*

app.include_router(settings_bank_accounts_router)
app.include_router(settings_company_router)
app.include_router(customers_router)
app.include_router(bank_transactions.router)
app.include_router(bank_import_router)
app.include_router(dossier_buyers_router)
app.include_router(transactions.router)  # <-- NEW
app.include_router(reports_router)
app.include_router(reports_export_router)
app.include_router(company_mailers.router)
app.include_router(auction_docs.router)
app.include_router(bid_tickets_router.router)

# Bid attendance (list/print) + exclusions (detail/exclude/clear)
app.include_router(bid_attendance_router.router)
app.include_router(bid_attendance_exclusions_router)

app.include_router(customer_documents_router)
app.include_router(announcements_router)
app.include_router(auction_results_router)
app.include_router(deposit_refunds.router)
app.include_router(auction_prints_router)
app.include_router(auction_counting_router)
app.include_router(auction_sessions_router)
app.include_router(auction_session_bid_sheets_router)
app.include_router(auction_session_winner_prints_router)
app.include_router(auction_session_display.router)
app.include_router(auction_documents_print_router)  # <-- NEW (attendance, future docs)

#Mobile
mount_mobile_routers(app)

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

    uvicorn.run('main:app', host="0.0.0.0", port=8887, reload=True)
