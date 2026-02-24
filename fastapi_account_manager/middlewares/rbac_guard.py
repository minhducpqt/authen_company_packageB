# fastapi_account_manager/middlewares/rbac_guard.py
import os
import httpx
from starlette.responses import RedirectResponse, JSONResponse

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")
ROLE_COOKIE_NAME = os.getenv("ROLE_COOKIE_NAME", "user_role")

AUTH_ME_PATH = os.getenv("AUTH_ME_PATH", "/auth/me")
AUTH_TIMEOUT = float(os.getenv("AUTH_HTTP_TIMEOUT", "5.0"))

# ===== Không áp RBAC =====
RBAC_ALLOW_PREFIXES = (
    "/static/",
    "/favicon.ico",
    "/login",
    "/healthz",
    "/apis/mobile/",  # ✅ NEW mobile gateway
)


# ===== ADMIN-ONLY PATHS (DENY LIST) =====
ADMIN_ONLY_PREFIXES = (
    "/reports",
    "/transactions/summary",
    "/projects/payment-accounts",
    "/announcements",
    "/settings",
    "/bid-attendance",
    "/bid-tickets",
    "/auction",
)

# ===== EXCEPTIONS: Non-admin vẫn được phép vào một số report export =====
REPORTS_NON_ADMIN_ALLOW_PREFIXES = (
    "/reports/dossiers/paid/detail/export",
    "/reports/dossiers/paid/summary/customer/export",
    "/reports/dossiers/paid/summary/types/export",
    "/projects/payment-accounts",
    "/auction",
    "/announcements"
)

# ===== Helpers =====

def _is_api_like(path: str) -> bool:
    return path.startswith("/api/") or path.endswith("/data")


def _normalize_path(path: str) -> str:
    """
    /api/xxx -> /xxx
    """
    if path.startswith("/api/"):
        p = path[4:]
        return p if p.startswith("/") else "/" + p
    return path


async def _get_role(request) -> str:
    # 1) cookie role (nhanh, đã set lúc login)
    rc = request.cookies.get(ROLE_COOKIE_NAME)
    if rc:
        return rc.upper().strip()

    # 2) fallback gọi Service A
    acc = request.cookies.get(ACCESS_COOKIE_NAME)
    if not acc:
        return "VIEWER"

    try:
        async with httpx.AsyncClient(
            base_url=SERVICE_A_BASE_URL,
            timeout=AUTH_TIMEOUT
        ) as client:
            r = await client.get(
                AUTH_ME_PATH,
                headers={"Authorization": f"Bearer {acc}"}
            )
        if r.status_code != 200:
            return "VIEWER"

        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        role = (
            data.get("role")
            or data.get("user_role")
            or (data.get("user") or {}).get("role")
        )
        return str(role).upper().strip() if role else "VIEWER"
    except Exception:
        return "VIEWER"


def _is_reports_exception_allowed_for_non_admin(path: str) -> bool:
    return any(path.startswith(p) for p in REPORTS_NON_ADMIN_ALLOW_PREFIXES)


def _is_admin_only(path: str) -> bool:
    # ✅ ngoại lệ: cho non-admin đi vào đúng các report export cần thiết
    if _is_reports_exception_allowed_for_non_admin(path):
        return False
    return any(path.startswith(p) for p in ADMIN_ONLY_PREFIXES)


def _redirect_non_admin_home():
    # Menu đầu tiên của non-admin
    return RedirectResponse(url="/transactions/dossiers", status_code=303)


def _redirect_super_admin_home():
    # ✅ SUPER_ADMIN landing page
    return RedirectResponse(url="/account", status_code=303)


# ===== Middleware =====

async def rbac_guard_middleware(request, call_next):
    path = request.url.path

    # Bỏ qua các path công khai
    if any(path.startswith(p) for p in RBAC_ALLOW_PREFIXES):
        return await call_next(request)

    role = await _get_role(request)

    # ✅ Nếu SUPER_ADMIN: sau login / landing -> đưa về /account
    # (Áp dụng cho các path "home" hay gặp sau login)
    if role == "SUPER_ADMIN":
        if path in ("/", "/login") or path.startswith("/login/"):
            return _redirect_super_admin_home()
        # SUPER_ADMIN toàn quyền, không hạn chế
        return await call_next(request)

    # ✅ COMPANY_ADMIN: không giới hạn gì cả
    if role == "COMPANY_ADMIN":
        return await call_next(request)

    # Normalize path để check logic
    logical_path = _normalize_path(path)

    # ❌ Non-admin + admin-only path => chặn
    if _is_admin_only(logical_path):
        if _is_api_like(path):
            return JSONResponse(
                {"error": "forbidden", "role": role},
                status_code=403
            )
        return _redirect_non_admin_home()

    # ✅ Còn lại cho qua hết
    return await call_next(request)
