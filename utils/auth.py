# utils/auth.py
import os
import httpx

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE_ENV  = os.getenv("ACCESS_COOKIE_NAME", "access_token")  # ví dụ: access_token

def get_access_token(request) -> str | None:
    """
    Lấy token theo thứ tự ưu tiên:
    - Header Authorization: Bearer <token>
    - Cookie 'access_token'
    - Cookie tên cấu hình qua ACCESS_COOKIE_NAME (nếu khác)
    """
    # 1) Header
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    # 2) Cookies phổ biến
    for name in ("access_token", ACCESS_COOKIE_ENV):
        tok = request.cookies.get(name)
        if tok:
            return tok

    return None


async def fetch_me(access_token: str | None):
    if not access_token:
        return None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=8.0) as client:
            r = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None
