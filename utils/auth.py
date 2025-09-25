# utils/auth.py
import os
import httpx
from typing import Optional

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")
ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")

def get_access_token(request) -> Optional[str]:
    # ưu tiên tên cookie từ .env; fallback "access_token"
    return request.cookies.get(ACCESS_COOKIE_NAME) or request.cookies.get("access_token")

async def fetch_me(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=6.0) as client:
            r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None
