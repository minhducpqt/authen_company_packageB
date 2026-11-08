"""Đọc menu đang áp dụng từ Service A. Lỗi hoặc chưa có bảng thì giữ menu cũ."""
from __future__ import annotations

import copy
import os
import time

import httpx

from utils.auth import account_menu_info, get_access_token

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
_TTL_SEC = 10.0
_cache: dict[tuple[str, str], tuple[float, dict]] = {}

_ALWAYS = (
    "/account",
    "/bieu-mau",
    "/huong-dan",
    "/logout",
    "/tien-ich-khac",
    "/quan-ly-tai-khoan",
)


def _one(path: str, prefix: str) -> bool:
    if prefix == "/":
        return path == "/"
    token = "{code}"
    if token in prefix:
        left, right = prefix.split(token, 1)
        if not path.startswith(left):
            return False
        rest = path[len(left):]
        cut = rest.find("/")
        if cut <= 0:
            return False
        tail = rest[cut:]
        return tail == right or tail.startswith(right + "/")
    return path == prefix or path.startswith(prefix + "/")


def rules_allow_path(path: str, rules: list) -> bool:
    for rule in rules or []:
        excludes = rule.get("excludes") or []
        if any(_one(path, prefix) for prefix in excludes):
            continue
        prefixes = rule.get("prefixes") or []
        if any(_one(path, prefix) for prefix in prefixes):
            return True
    return False


def always_allowed(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _ALWAYS)


def item_active(kind: str, href: str, path: str) -> bool:
    path = path or "/"
    if kind == "reports":
        return path in ("/", "/reports") or path.startswith("/reports")
    if kind == "projects":
        return path.startswith("/projects") and not path.startswith("/projects/payment-accounts")
    if kind == "customers":
        return path.startswith("/customers") and not path.startswith("/customers/documents")
    if kind == "billing":
        return path.startswith("/billing") and not path.startswith("/billing/admin")
    if kind == "sessions":
        return (
            path.startswith("/auction/sessions")
            or path.startswith("/auction-sessions")
            or path.startswith("/auction/counting")
        )
    return path == href or path.startswith((href or "") + "/")


def _mark(groups: list, path: str) -> None:
    for group in groups or []:
        for item in group.get("items") or []:
            item["active"] = item_active(item.get("active_kind") or "prefix", item.get("href") or "", path)


async def resolve_nav(request, role: str) -> dict:
    """legacy=True nghĩa là dùng menu và chặn trang y như trước khi có cấu hình."""
    fallback = {"legacy": True, "groups": [], "rules": [], "label": "", "first_href": "/transactions/dossiers"}
    role_u = (role or "").upper()
    if role_u == "SUPER_ADMIN":
        return fallback
    info = account_menu_info(request)
    company = (info.get("company_code") or "").strip().lower()
    key = (role_u, company)
    now = time.monotonic()
    hit = _cache.get(key)
    if hit and now - hit[0] < _TTL_SEC:
        data = copy.deepcopy(hit[1])
    else:
        token = get_access_token(request)
        data = fallback
        if token:
            try:
                async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=2.5) as client:
                    resp = await client.get(
                        "/api/v1/admin/menu-roles/mine",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                if resp.status_code == 200:
                    body = resp.json()
                    if isinstance(body, dict) and "legacy" in body:
                        data = body
            except Exception:
                data = fallback
        _cache[key] = (now, copy.deepcopy(data))
    if data.get("legacy"):
        data["groups"] = []
        return data
    _mark(data.get("groups") or [], request.url.path)
    return data
