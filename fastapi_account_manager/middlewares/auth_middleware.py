from fastapi_authen.settings import AuthSettings
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import RedirectResponse, Response
from starlette.requests import Request
import httpx

settings = AuthSettings()

# ✅ Bao đủ các đường dẫn có thể đi qua middleware của sub-app
WHITELIST_PREFIXES = (
    "/accounts/login",  # login UI khi đã mount /accounts
    "/login",           # đề phòng chạy sub-app độc lập
    "/accounts/static",
    "/static",
    "/auth/login",      # API login của Module A (ở root)
    "/auth/refresh",    # API refresh của Module A (ở root)
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        path = request.url.path

        if any(path.startswith(p) for p in WHITELIST_PREFIXES):
            return await call_next(request)

        if not request.cookies.get(settings.ACCESS_COOKIE_NAME):
            return RedirectResponse(url="/accounts/login")  # đường dẫn PUBLIC sau khi mount

        response: Response = await call_next(request)

        if response.status_code == 401:
            async with httpx.AsyncClient(base_url=str(request.base_url)) as client:
                refresh_resp = await client.post("/auth/refresh", cookies=request.cookies)
                if refresh_resp.status_code == 200:
                    for k, v in refresh_resp.cookies.items():
                        response.set_cookie(
                            key=k, value=v,
                            httponly=True,
                            secure=settings.COOKIE_SECURE,
                            samesite=settings.COOKIE_SAMESITE,
                            path="/" if k == settings.ACCESS_COOKIE_NAME else "/auth",
                        )
                    response = await call_next(request)
                else:
                    return RedirectResponse(url="/accounts/login")

        return response
