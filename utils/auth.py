# utils/auth.py
import base64
import json
import os
from typing import Any, Dict, Optional

import httpx

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
ACCESS_COOKIE_ENV = os.getenv("ACCESS_COOKIE_NAME", "access_token")  # ví dụ: access_token

# Cookie hiển thị menu tài khoản (không dùng cho auth/RBAC)
UI_USERNAME_COOKIE = os.getenv("UI_USERNAME_COOKIE", "ui_username")
UI_COMPANY_COOKIE = os.getenv("UI_COMPANY_COOKIE", "ui_company")

_ROLE_LABELS = {
    "SUPER_ADMIN": "Super admin",
    "COMPANY_ADMIN": "Quản trị công ty",
    "STAFF": "Nhân viên",
    "VIEWER": "Chỉ xem",
    "ACCOUNTANT": "Kế toán",
}


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


def _jwt_payload_unverified(token: str) -> Dict[str, Any]:
    """Chỉ để hiển thị UI — không verify chữ ký (auth đã do middleware xử lý)."""
    try:
        parts = (token or "").split(".")
        if len(parts) < 2:
            return {}
        pad = "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(parts[1] + pad)
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def set_ui_profile_cookies(
    resp,
    *,
    username: Optional[str],
    company_code: Optional[str],
    secure: bool = False,
    samesite: str = "Lax",
    path: str = "/",
) -> None:
    """Ghi cookie nhẹ cho menu tài khoản."""
    base = {
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "path": path,
    }
    u = (username or "").strip()
    cc = (company_code or "").strip()
    if u:
        resp.set_cookie(key=UI_USERNAME_COOKIE, value=u, **base)
    else:
        resp.delete_cookie(UI_USERNAME_COOKIE, path=path)
    if cc:
        resp.set_cookie(key=UI_COMPANY_COOKIE, value=cc, **base)
    else:
        resp.delete_cookie(UI_COMPANY_COOKIE, path=path)


def clear_ui_profile_cookies(resp, path: str = "/") -> None:
    resp.delete_cookie(UI_USERNAME_COOKIE, path=path)
    resp.delete_cookie(UI_COMPANY_COOKIE, path=path)


def account_menu_info(request) -> Dict[str, Any]:
    """
    Dữ liệu header menu.
    Ưu tiên: request.state.auth_me (đã có từ auth_guard /auth/me) → cookie UI → JWT claims.
    Không gọi thêm Service A.
    """
    role = (request.cookies.get("user_role") or "VIEWER").strip().upper()
    username = (request.cookies.get(UI_USERNAME_COOKIE) or "").strip() or None
    company_code = (request.cookies.get(UI_COMPANY_COOKIE) or "").strip() or None

    # /auth/me đã chạy ở middleware (cùng request) → có username.real e.g. daiduong.minhduc
    me: Dict[str, Any] = {}
    try:
        raw = getattr(request.state, "auth_me", None)
        if isinstance(raw, dict):
            me = raw
    except Exception:
        me = {}

    if me:
        nested = me.get("user") if isinstance(me.get("user"), dict) else {}
        profile = me.get("profile") if isinstance(me.get("profile"), dict) else {}
        me_user = (
            me.get("username")
            or nested.get("username")
            or profile.get("username")
            or me.get("user_name")
            or me.get("login")
            or ""
        )
        me_user = str(me_user).strip() if me_user is not None else ""
        if me_user and not me_user.isdigit():
            username = me_user

        me_cc = (
            me.get("company_code")
            or nested.get("company_code")
            or profile.get("company_code")
            or me.get("company")
            or ""
        )
        me_cc = str(me_cc).strip() if me_cc is not None else ""
        if me_cc:
            company_code = me_cc

        me_role = (
            me.get("role")
            or me.get("user_role")
            or nested.get("role")
            or profile.get("role")
            or ""
        )
        me_role = str(me_role).upper().strip() if me_role else ""
        if me_role:
            role = me_role

    tok = get_access_token(request)
    if tok:
        claims = _jwt_payload_unverified(tok)
        if not company_code:
            company_code = (
                claims.get("company_code") or claims.get("company") or ""
            ).strip() or None
        if not username:
            claim_u = (
                claims.get("username") or claims.get("preferred_username") or ""
            ).strip()
            # sub thường là user id (số) — không hiển thị
            if claim_u and not claim_u.isdigit():
                username = claim_u

    return {
        "username": username,
        "company_code": company_code,
        "role": role,
        "role_label": _ROLE_LABELS.get(role, role or "—"),
    }
