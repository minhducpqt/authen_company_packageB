# fastapi_account_manager/middlewares/auth_guard.py
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from starlette.requests import Request
import httpx
import urllib.parse
import os

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")

# Các path không cần login
ALLOW_LIST = {"/healthz", "/docs", "/openapi.json"}
ALLOW_PREFIXES = ("/static/", "/favicon.ico")

class AuthGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Cho qua trang login (GET/POST) và các path tĩnh/cho phép
        if path == "/login" or path in ALLOW_LIST or any(path.startswith(p) for p in ALLOW_PREFIXES):
            return await call_next(request)

        # Lấy access token từ cookie
        acc = request.cookies.get(ACCESS_COOKIE_NAME)
        if not acc:
            return self._redirect_to_login(request)

        # Check phiên với Service A: /auth/me
        try:
            async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=5.0) as client:
                r = await client.get("/auth/me", headers={"Authorization": f"Bearer {acc}"})
            if r.status_code == 200:
                return await call_next(request)
        except Exception:
            # lỗi backend: gửi về login
            return self._redirect_to_login(request)

        # Không hợp lệ -> login
        return self._redirect_to_login(request)

    def _redirect_to_login(self, request: Request) -> RedirectResponse:
        # Chỉ lấy đường dẫn + query tương đối (không dùng absolute URL)
        path = request.url.path or "/"
        qs = request.url.query
        next_rel = path + (f"?{qs}" if qs else "")
        next_enc = urllib.parse.quote(next_rel, safe="")
        return RedirectResponse(url=f"/login?next={next_enc}", status_code=303)
