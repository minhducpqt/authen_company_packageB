from __future__ import annotations

from fastapi import FastAPI

# ==== Mobile APIs (absolute imports) ====
from routers.mobile.apis.v1.mobile_auth import router as mobile_auth_router
from routers.mobile.apis.v1.mobile_customers import router as mobile_customers_router

def mount_routers(app: FastAPI) -> None:
    # New (v1)
    app.include_router(mobile_auth_router, prefix="/api/mobile/v1")
    app.include_router(mobile_customers_router, prefix="/api/mobile/v1")

    # Optional: giữ legacy để khỏi gãy cái đang test
    app.include_router(mobile_auth_router, prefix="/api/mobile")
    app.include_router(mobile_customers_router, prefix="/api/mobile")
