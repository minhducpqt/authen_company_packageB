# fastapi_account_manager/middlewares/auth_guard.py
import os
import urllib.parse
import httpx
from starlette.responses import RedirectResponse

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")

AUTH_ME_PATH = os.getenv("AUTH_ME_PATH", "/auth/me")
AUTH_REFRESH_PATH = os.getenv("AUTH_REFRESH_PATH", "/auth/refresh")
AUTH_REFRESH_METHOD = os.getenv("AUTH_REFRESH_METHOD", "POST").upper()  # POST/GET

AUTH_TIMEOUT = float(os.getenv("AUTH_HTTP_TIMEOUT", "5.0"))

# Các path được phép không cần login
ALLOW_LIST = {
    "/healthz",
    "/docs",
    "/openapi.json",
}

# ✅ Thêm '/transactions/' vào prefix cho qua
ALLOW_PREFIXES = (
    "/static/",
    "/favicon.ico",
    "/login",
    "/apis/mobile/",  # ✅ NEW mobile gateway
)


async def auth_guard_middleware(request, call_next):
    path = request.url.path

    # Cho qua các path tĩnh / login / cho phép
    if path in ALLOW_LIST or any(path.startswith(p) for p in ALLOW_PREFIXES):
        return await call_next(request)

    # 1) Nếu có access -> check /auth/me
    acc = request.cookies.get(ACCESS_COOKIE_NAME)
    if acc:
        ok = await _check_me(acc)
        if ok:
            return await call_next(request)

        # access fail (thường hết hạn) -> thử refresh
        set_cookies = await _try_refresh(request)
        if not set_cookies:
            return _redirect_to_login(request)

        resp = await call_next(request)
        _attach_set_cookies(resp, set_cookies)
        return resp

    # 2) Không có access -> thử refresh luôn (nếu có refresh cookie)
    set_cookies = await _try_refresh(request)
    if not set_cookies:
        return _redirect_to_login(request)

    resp = await call_next(request)
    _attach_set_cookies(resp, set_cookies)
    return resp


async def _check_me(access_token: str) -> bool:
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=AUTH_TIMEOUT) as client:
            r = await client.get(AUTH_ME_PATH, headers={"Authorization": f"Bearer {access_token}"})
        return r.status_code == 200
    except Exception as e:
        print("[AUTH] /auth/me exception:", e)
        return False


async def _try_refresh(request):
    """
    Gọi /auth/refresh bằng refresh cookie từ request.
    Nếu thành công, trả về list Set-Cookie headers để forward về browser.
    """
    ref = request.cookies.get(REFRESH_COOKIE_NAME)
    if not ref:
        return None

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=AUTH_TIMEOUT) as client:
            if AUTH_REFRESH_METHOD == "GET":
                rr = await client.get(AUTH_REFRESH_PATH, cookies={REFRESH_COOKIE_NAME: ref})
            else:
                rr = await client.post(AUTH_REFRESH_PATH, cookies={REFRESH_COOKIE_NAME: ref})

        if rr.status_code != 200:
            return None

        try:
            return rr.headers.get_list("set-cookie")
        except Exception:
            # fallback an toàn
            sc = rr.headers.get("set-cookie")
            return [sc] if sc else []
    except Exception as e:
        print("[AUTH] /auth/refresh exception:", e)
        return None


def _attach_set_cookies(response, set_cookies):
    if not set_cookies:
        return
    for c in set_cookies:
        if c:
            response.headers.append("set-cookie", c)


def _redirect_to_login(request):
    path = request.url.path or "/"
    qs = request.url.query
    next_rel = path + (f"?{qs}" if qs else "")
    next_enc = urllib.parse.quote(next_rel, safe="")
    return RedirectResponse(url=f"/login?next={next_enc}", status_code=303)
