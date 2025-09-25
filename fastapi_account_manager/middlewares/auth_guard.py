# fastapi_account_manager/middlewares/auth_guard.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from starlette.requests import Request
import httpx
import urllib.parse
import os

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")
ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")

# Các path không cần login
ALLOW_LIST = {
    "/login",
    "/healthz",
    "/docs",
    "/openapi.json",
}
# Static prefixes
ALLOW_PREFIXES = (
    "/static/",
    "/favicon.ico",
)

class AuthGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in ALLOW_LIST or any(path.startswith(p) for p in ALLOW_PREFIXES):
            return await call_next(request)

        # Lấy access token từ cookie
        acc = request.cookies.get(ACCESS_COOKIE_NAME)
        if not acc:
            return self._redirect_to_login(request)

        # Check phiên với Service A: /auth/me
        try:
            async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=5.0) as client:
                r = await client.get(
                    "/auth/me",
                    headers={"Authorization": f"Bearer {acc}"}
                )
            if r.status_code == 200:
                # ok -> cho qua
                return await call_next(request)
        except Exception:
            # Lỗi kết nối backend -> cho về login để tránh vòng lặp lỗi
            return self._redirect_to_login(request)

        # Không hợp lệ -> quay về login
        return self._redirect_to_login(request)

    def _redirect_to_login(self, request: Request) -> RedirectResponse:
        next_url = urllib.parse.quote(str(request.url))
        return RedirectResponse(url=f"/login?next={next_url}", status_code=303)
