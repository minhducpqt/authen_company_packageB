# routers/auction_documents_print.py  (Service B - Admin Portal)
from __future__ import annotations

import os
from typing import Any, Dict, Optional, List

import httpx
from fastapi import APIRouter, Request, Path, Query
from fastapi.responses import HTMLResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["auction_sessions:documents_print"])

# Nếu muốn ép gọi nội bộ qua localhost (ổn định khi SSR / reverse proxy)
# ví dụ: SERVICE_B_BASE_URL="http://127.0.0.1:8887"
SERVICE_B_BASE_URL = os.getenv("SERVICE_B_BASE_URL", "").strip()

# Optional: header org name/note in print template
ORG_NAME = os.getenv("AUCTION_ORG_NAME", "").strip() or os.getenv("ORG_NAME", "").strip()
ORG_NOTE = os.getenv("AUCTION_ORG_NOTE", "").strip() or os.getenv("ORG_NOTE", "").strip()

# =========================================================
# Logging helpers (mask sensitive)
# =========================================================
_SENSITIVE_KEYS = {"phone", "cccd", "token", "access_token", "authorization", "cookie"}


def _log(msg: str) -> None:
    print(f"[AUCTION_DOCS_PRINT_B] {msg}")


def _mask(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k and str(k).lower() in _SENSITIVE_KEYS:
                out[k] = "***"
            else:
                out[k] = _mask(v)
        return out
    if isinstance(obj, list):
        return [_mask(x) for x in obj]
    return obj


def _base_url_from_request(request: Request) -> str:
    # Ưu tiên env nếu có (ổn định trong SSR / reverse proxy)
    if SERVICE_B_BASE_URL:
        return SERVICE_B_BASE_URL.rstrip("/")
    # fallback: lấy theo request (có thể là domain public)
    return str(request.base_url).rstrip("/")


async def _b_get_json(
    request: Request,
    path: str,
    token: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Gọi API nội bộ của Service B (chính app này).
    IMPORTANT:
    - Forward cookies của request gốc => tránh 303 redirect /login
      (vì nhiều endpoint của B lấy access token từ cookie/session)
    - Đồng thời vẫn gửi Authorization: Bearer {token} để tương thích tương lai.
    """
    base = _base_url_from_request(request)
    url = f"{base}{path}"

    headers = {"Authorization": f"Bearer {token}"}

    # forward cookies từ request gốc để tránh bị 303
    cookies = dict(request.cookies or {})

    _log(f"GET {url} params={_mask(params or {})} cookies_keys={list(cookies.keys())}")

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        try:
            r = await client.get(url, headers=headers, params=params or {}, cookies=cookies)
        except Exception as e:
            _log(f"EXC GET {url}: {e}")
            raise RuntimeError(f"HTTP client error calling {path}: {e}") from e

    # 303 thường là redirect về /login nếu token/cookie không hợp lệ
    if r.status_code in (301, 302, 303, 307, 308):
        loc = r.headers.get("location") or ""
        raise RuntimeError(f"AUTH_REDIRECT ({r.status_code}) -> {loc or '(no location)'}")

    try:
        js = r.json()
    except Exception:
        js = {"detail": (r.text or "")[:800]}

    if r.status_code >= 400:
        detail = js.get("detail") if isinstance(js, dict) else None
        raise RuntimeError(detail or f"HTTP {r.status_code} calling {path}")

    return js if isinstance(js, dict) else {"data": js}


def _get_nested(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    try:
        return str(v)
    except Exception:
        return ""


def _build_print_items(attendance_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert payload rows from attendance API into template-friendly items.
    attendance row sample:
      {
        "customer_id": ...,
        "stt": ...,
        "customer": {...snapshot...},
        "refund_bank_accounts": {...} or null,
        "lot_count": n
      }
    """
    out: List[Dict[str, Any]] = []
    for r in attendance_rows or []:
        cust = r.get("customer") if isinstance(r.get("customer"), dict) else {}
        refund = r.get("refund_bank_accounts") if isinstance(r.get("refund_bank_accounts"), dict) else {}

        full_name = _to_str(
            cust.get("customer_full_name")
            or cust.get("full_name")
            or cust.get("name")
        ).strip()

        address = _to_str(cust.get("address") or cust.get("address_short") or "").strip()
        cccd = _to_str(cust.get("cccd") or "").strip()
        phone = _to_str(cust.get("phone") or "").strip()

        bank_short = _to_str(
            refund.get("bank_shortname")
            or refund.get("bank_name")
            or refund.get("bank_code")
            or ""
        ).strip()

        acc_no = _to_str(refund.get("account_number") or refund.get("account_no") or "").strip()
        acc_name = _to_str(refund.get("account_name") or "").strip()

        item = {
            "stt": r.get("stt"),
            "customer_full_name": full_name,
            "address_short": address,
            "cccd": cccd,
            "phone": phone,
            "refund_bank_shortname": bank_short,
            "refund_account_no": acc_no,
            "refund_account_name": acc_name,
            "lot_count": r.get("lot_count") or 0,
        }
        out.append(item)
    return out


# =========================================================
# PRINT: Attendance list (A4)
# =========================================================
@router.get(
    "/auction/sessions/{session_id}/documents/attendance/print",
    response_class=HTMLResponse,
)
async def print_attendance_list(
    request: Request,
    session_id: int = Path(..., ge=1),
    title: Optional[str] = Query(None),
):
    """
    In danh sách điểm danh người tham gia đấu giá (A4).

    Router này KHÔNG gọi Service A trực tiếp.
    Nó gọi API nội bộ của Service B:
      GET /auction/sessions/api/sessions/{session_id}/attendance
    API này trả: { ok, session, data }
    """
    token = get_access_token(request)
    if not token:
        return templates.TemplateResponse(
            "pages/error.html",
            {
                "request": request,
                "title": "Chưa đăng nhập",
                "message": "Vui lòng đăng nhập lại.",
            },
            status_code=401,
        )

    error: Optional[Dict[str, Any]] = None
    attendance: Dict[str, Any] = {}

    try:
        attendance = await _b_get_json(
            request=request,
            path=f"/auction/sessions/api/sessions/{session_id}/attendance",
            token=token,
            params=None,
            timeout=30.0,
        )
    except Exception as e:
        msg = str(e)
        _log(f"ERROR load attendance: {msg}")
        error = {"message": msg}
        attendance = {}

    sess = (attendance or {}).get("session") or {}
    rows = (attendance or {}).get("data") or []

    # Build variables expected by your template
    project = {
        "name": sess.get("project_name") or sess.get("project_code") or "",
        "project_code": sess.get("project_code") or "",
    }
    stats = {
        "total_lots": sess.get("lot_count") or 0,
        "total_customers": sess.get("customer_count") or 0,
    }
    items = _build_print_items(rows)

    return templates.TemplateResponse(
        "pages/auction_session_documents/attendance_print.html",
        {
            "request": request,
            "title": title or "Danh sách điểm danh người tham gia đấu giá",
            "session_id": session_id,

            # raw payload (optional debug)
            "attendance": attendance or {},

            # template variables (matching your HTML)
            "session": sess,
            "project": project,
            "stats": stats,
            "items": items,

            # optional org header
            "org_name": ORG_NAME,
            "org_note": ORG_NOTE,

            # error payload
            "error": error,
        },
    )
