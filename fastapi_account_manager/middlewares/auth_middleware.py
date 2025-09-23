from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
import httpx
from fastapi_authen.settings import AuthSettings

settings = AuthSettings()

WHITELIST_PREFIXES = ("/auth/login", "/auth/refresh", "/accounts/static")

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        path = request.url.path

        # allow auth & static
        if any(path.startswith(p) for p in WHITELIST_PREFIXES):
            return await call_next(request)

        # must have access cookie, otherwise go to login
        if not request.cookies.get(settings.ACCESS_COOKIE_NAME):
            return RedirectResponse(url="/auth/login")

        response: Response = await call_next(request)

        # if access expired -> try refresh then retry once
        if response.status_code == 401:
            async with httpx.AsyncClient(base_url=str(request.base_url)) as client:
                refresh_resp = await client.post("/auth/refresh", cookies=request.cookies)
                if refresh_resp.status_code == 200:
                    # propagate new cookies
                    for k, v in refresh_resp.cookies.items():
                        response.set_cookie(
                            key=k, value=v,
                            httponly=True,
                            secure=settings.COOKIE_SECURE,
                            samesite=settings.COOKIE_SAMESITE,
                            path="/" if k == settings.ACCESS_COOKIE_NAME else "/auth",
                        )
                    # retry original
                    response = await call_next(request)
                else:
                    return RedirectResponse(url="/auth/login")

        return response
