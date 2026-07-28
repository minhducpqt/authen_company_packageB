# utils/device_cookie.py
"""Cookie tin cậy OTP theo từng username (tránh ghi đè khi đổi tài khoản trên cùng browser)."""
from __future__ import annotations

import hashlib
import os

from fastapi import Request
from fastapi.responses import RedirectResponse

# Service A vẫn đọc tên cookie chuẩn khi B proxy qua httpx.
LEGACY_DEVICE_COOKIE_NAME = os.getenv("DEVICE_COOKIE_NAME", "device_id")
DEVICE_COOKIE_PREFIX = os.getenv("DEVICE_COOKIE_PREFIX", "device_id_u_")

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "Lax")
DEVICE_COOKIE_MAX_AGE = 365 * 24 * 3600


def device_cookie_key_for_username(username: str) -> str:
    u = (username or "").strip().lower()
    digest = hashlib.sha256(u.encode("utf-8")).hexdigest()[:24]
    return f"{DEVICE_COOKIE_PREFIX}{digest}"


def read_device_id_for_user(request: Request, username: str) -> str | None:
    """Ưu tiên cookie theo user; fallback cookie legacy (migration)."""
    key = device_cookie_key_for_username(username)
    did = (request.cookies.get(key) or "").strip()
    if did:
        return did
    legacy = (request.cookies.get(LEGACY_DEVICE_COOKIE_NAME) or "").strip()
    return legacy or None


def forward_device_cookies(request: Request, username: str) -> dict[str, str]:
    did = read_device_id_for_user(request, username)
    if did:
        return {LEGACY_DEVICE_COOKIE_NAME: did}
    return {}


def set_device_cookie_for_user(
    resp: RedirectResponse,
    username: str,
    device_id: str | None,
) -> None:
    did = (device_id or "").strip()
    u = (username or "").strip()
    if not did or not u:
        return
    resp.set_cookie(
        key=device_cookie_key_for_username(u),
        value=did,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=DEVICE_COOKIE_MAX_AGE,
        path="/",
    )


def clear_device_cookies_for_user(resp: RedirectResponse, username: str | None) -> None:
    u = (username or "").strip()
    if u:
        resp.delete_cookie(device_cookie_key_for_username(u), path="/")
    resp.delete_cookie(LEGACY_DEVICE_COOKIE_NAME, path="/")
