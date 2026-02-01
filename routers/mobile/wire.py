from __future__ import annotations

from fastapi import FastAPI

# Mirror router (proxy all A endpoints)
from routers.mobile.apis.v1.mirror import router as mobile_mirror_router


def mount_routers(app: FastAPI) -> None:
    # =========================
    # NEW: /apis/mobile/v1  ✅
    # Mobile app will call:
    #   {B_BASE}/apis/mobile/v1/{A_ENDPOINT}
    # Example:
    #   /apis/mobile/v1/api/v1/projects
    # =========================
    app.include_router(mobile_mirror_router, prefix="/apis/mobile/v1")

    # =========================
    # KEEP: /api/mobile/v1 (legacy/test)
    # =========================

    app.include_router(mobile_mirror_router, prefix="/api/mobile/v1")

    # =========================
    # KEEP: /api/mobile (legacy/test)
    # =========================
    app.include_router(mobile_mirror_router, prefix="/api/mobile")
