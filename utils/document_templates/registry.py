# utils/document_templates/registry.py
"""
Chọn mẫu giấy tờ in HTML theo công ty.

- Công ty không có entry trong COMPANY_TEMPLATES → dùng DEFAULT_TEMPLATES (mẫu hiện tại).
- Thêm mẫu riêng: tạo file HTML trong templates/.../custom/{company}/ rồi khai báo ở COMPANY_TEMPLATES.

Ví dụ KINHDO hiện dùng mẫu default (không khai báo override).
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class DocKind:
    REGISTRATION = "registration"
    BID_SHEET = "bid_sheet"
    WINNER_CONFIRM = "winner_confirm"
    WINNER_SLIP = "winner_slip"
    WINNER_SLIPS_PROJECT = "winner_slips_project"
    ATTENDANCE_PRE = "attendance_pre"
    ATTENDANCE_SESSION = "attendance_session"
    ATTENDANCE_PUBLIC_NOTICE = "attendance_public_notice"


DEFAULT_TEMPLATES: Dict[str, str] = {
    DocKind.REGISTRATION: "pages/documents/auction_registration.html",
    DocKind.BID_SHEET: "pages/auction_session_documents/bid_sheet_print.html",
    DocKind.WINNER_CONFIRM: "pages/auction_session_documents/winner_print.html",
    DocKind.WINNER_SLIP: "auction/winner_slip.html",
    DocKind.WINNER_SLIPS_PROJECT: "auction/winner_slips_project.html",
    DocKind.ATTENDANCE_PRE: "pages/bid_attendance/print.html",
    DocKind.ATTENDANCE_SESSION: "pages/auction_session_documents/attendance_print.html",
    DocKind.ATTENDANCE_PUBLIC_NOTICE: (
        "pages/auction_session_documents/attendance_public_notice.html"
    ),
}

# company_code (lower) → { doc_kind → template path (Jinja, relative templates root) }
COMPANY_TEMPLATES: Dict[str, Dict[str, str]] = {
    # "kinhdo": {
    #     DocKind.REGISTRATION: DEFAULT_TEMPLATES[DocKind.REGISTRATION],
    #     ...
    # },
}


def company_code_from_me(me: Optional[Dict[str, Any]]) -> str:
    if not me:
        return ""
    raw = (
        me.get("company_code")
        or me.get("company")
        or me.get("companyCode")
        or ""
    )
    return str(raw).strip().lower()


def extract_company_code(
    *,
    me: Optional[Dict[str, Any]] = None,
    company: Optional[Dict[str, Any]] = None,
    project: Optional[Dict[str, Any]] = None,
    session: Optional[Dict[str, Any]] = None,
) -> str:
    candidates = []
    if me:
        candidates.append(company_code_from_me(me))
    if company:
        candidates.append(company.get("company_code") or company.get("code"))
    if project:
        candidates.append(project.get("company_code") or project.get("code"))
    if session:
        candidates.append(session.get("company_code"))
    for raw in candidates:
        s = str(raw or "").strip().lower()
        if s:
            return s
    return ""


def resolve_template(company_code: Optional[str], doc_kind: str) -> str:
    """
    Trả về đường dẫn template Jinja.
    Luôn fallback về DEFAULT_TEMPLATES nếu không có override.
    """
    cc = (company_code or "").strip().lower()
    if cc:
        custom = (COMPANY_TEMPLATES.get(cc) or {}).get(doc_kind)
        if custom:
            return custom
    default = DEFAULT_TEMPLATES.get(doc_kind)
    if not default:
        raise ValueError(f"Unknown doc_kind: {doc_kind}")
    return default
