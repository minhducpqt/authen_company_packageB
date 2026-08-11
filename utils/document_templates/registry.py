# utils/document_templates/registry.py
"""
Chọn mẫu giấy tờ in HTML theo công ty.

Cấu trúc template (relative templates/):
  pages/documents/default/     — mẫu mặc định (tất cả công ty không override)
  pages/documents/kinhdo/      — mẫu riêng KINHDO (đặt cùng tên file)
  pages/documents/kido/        — mẫu riêng KIDO
  pages/documents/vnt/         — mẫu riêng VNT
  pages/documents/{company}/   — công ty khác

Tên file theo DocKind (xem TEMPLATE_FILES).

Resolve:
  1. COMPANY_TEMPLATES (hardcode path tường minh, nếu có)
  2. File tồn tại trong pages/documents/{company}/ → dùng tự động
  3. Fallback pages/documents/default/
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

# templates/ root (Service B)
_TEMPLATES_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "templates")
)

_DOCUMENTS_ROOT = "pages/documents"


class DocKind:
    REGISTRATION_NORMAL = "registration_normal"
    REGISTRATION_GROUP = "registration_group"
    REGISTRATION_GROUP_PRE_SESSION = "registration_group_pre_session"
    BID_SHEET = "bid_sheet"
    WINNER_CONFIRM = "winner_confirm"
    WINNER_SLIP = "winner_slip"
    WINNER_SLIPS_PROJECT = "winner_slips_project"
    ATTENDANCE_PRE = "attendance_pre"
    ATTENDANCE_SESSION = "attendance_session"
    ATTENDANCE_PUBLIC_NOTICE = "attendance_public_notice"
    ATTENDANCE_SEAT_LABELS = "attendance_seat_labels"
    WINNER_SIGN_LIST = "winner_sign_list"


TEMPLATE_FILES: Dict[str, str] = {
    DocKind.REGISTRATION_NORMAL: "registration_normal.html",
    DocKind.REGISTRATION_GROUP: "registration_group.html",
    DocKind.REGISTRATION_GROUP_PRE_SESSION: "registration_group_pre_session.html",
    DocKind.BID_SHEET: "bid_sheet.html",
    DocKind.WINNER_CONFIRM: "winner_confirm.html",
    DocKind.WINNER_SLIP: "winner_slip.html",
    DocKind.WINNER_SLIPS_PROJECT: "winner_slips_project.html",
    DocKind.ATTENDANCE_PRE: "attendance_pre.html",
    DocKind.ATTENDANCE_SESSION: "attendance_session.html",
    DocKind.ATTENDANCE_PUBLIC_NOTICE: "attendance_public_notice.html",
    DocKind.ATTENDANCE_SEAT_LABELS: "attendance_seat_labels.html",
    DocKind.WINNER_SIGN_LIST: "winner_sign_list.html",
}


def default_template_path(doc_kind: str) -> str:
    fname = TEMPLATE_FILES[doc_kind]
    return f"{_DOCUMENTS_ROOT}/default/{fname}"


def company_template_path(company_code: str, doc_kind: str) -> str:
    cc = (company_code or "").strip().lower()
    fname = TEMPLATE_FILES[doc_kind]
    return f"{_DOCUMENTS_ROOT}/{cc}/{fname}"


DEFAULT_TEMPLATES: Dict[str, str] = {
    kind: default_template_path(kind) for kind in TEMPLATE_FILES
}

# Override tường minh (tuỳ chọn — nếu tên file khác convention)
COMPANY_TEMPLATES: Dict[str, Dict[str, str]] = {
    # "kinhdo": {
    #     DocKind.REGISTRATION_NORMAL: company_template_path("kinhdo", DocKind.REGISTRATION_NORMAL),
    # },
}


def _template_file_exists(rel_path: str) -> bool:
    return os.path.isfile(os.path.join(_TEMPLATES_ROOT, rel_path))


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
    if doc_kind not in TEMPLATE_FILES:
        raise ValueError(f"Unknown doc_kind: {doc_kind}")

    cc = (company_code or "").strip().lower()
    if cc:
        explicit = (COMPANY_TEMPLATES.get(cc) or {}).get(doc_kind)
        if explicit:
            return explicit
        company_rel = company_template_path(cc, doc_kind)
        if _template_file_exists(company_rel):
            return company_rel

    return default_template_path(doc_kind)


def resolve_registration_template(
    company_code: Optional[str],
    registration_mode: Optional[str] = None,
    lot_policy: Optional[str] = None,
) -> str:
    """Chọn mẫu phiếu đăng ký theo công ty, hình thức đấu và lot_policy đấu nhóm."""
    mode = (registration_mode or "NORMAL").strip().upper()
    if mode == "GROUP_AUCTION":
        policy = (lot_policy or "IN_SESSION_R1").strip().upper()
        doc_kind = (
            DocKind.REGISTRATION_GROUP_PRE_SESSION
            if policy == "PRE_SESSION"
            else DocKind.REGISTRATION_GROUP
        )
    else:
        doc_kind = DocKind.REGISTRATION_NORMAL
    return resolve_template(company_code, doc_kind)
