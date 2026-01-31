from __future__ import annotations

from fastapi import FastAPI

# ==== Mobile APIs (absolute imports) ====
from routers.mobile.apis.mobile_auth import router as mobile_auth_router
from routers.mobile.apis.mobile_customers import router as mobile_customers_router


def mount_routers(app: FastAPI) -> None:
    """
    Mount all mobile APIs (giống pattern app/routers/wire.py của Service A).
    Dùng absolute import để tránh lỗi relative import khi chạy uvicorn/gunicorn.
    """

    # --- Mobile Auth ---
    app.include_router(mobile_auth_router, prefix="/api/mobile")

    # --- Mobile Customers ---
    app.include_router(mobile_customers_router, prefix="/api/mobile")
