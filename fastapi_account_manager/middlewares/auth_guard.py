# fastapi_account_manager/middlewares/auth_guard.py
import os, urllib.parse, httpx
from starlette.responses import RedirectResponse

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")

# Các path được phép không cần login
ALLOW_LIST = {
    "/healthz", "/docs", "/openapi.json",
    "/giao-dich-ngan-hang", "/giao-dich-ngan-hang/data", "/giao-dich-ngan-hang/import",
    "/bank/txns",
}
ALLOW_PREFIXES = ("/static/", "/favicon.ico", "/login")

async def auth_guard_middleware(request, call_next):
    path = request.url.path

    # Cho qua các path tĩnh / login / cho phép
    if path in ALLOW_LIST or any(path.startswith(p) for p in ALLOW_PREFIXES):
        return await call_next(request)

    acc = request.cookies.get(ACCESS_COOKIE_NAME)
    if not acc:
        return _redirect_to_login(request)

    # Check token hợp lệ với Service A
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=5.0) as client:
            r = await client.get("/auth/me", headers={"Authorization": f"Bearer {acc}"})
        if r.status_code == 200:
            return await call_next(request)
    except Exception as e:
        print("[AUTH] Exception:", e)

    return _redirect_to_login(request)


def _redirect_to_login(request):
    path = request.url.path or "/"
    qs = request.url.query
    next_rel = path + (f"?{qs}" if qs else "")
    next_enc = urllib.parse.quote(next_rel, safe="")
    return RedirectResponse(url=f"/login?next={next_enc}", status_code=303)
