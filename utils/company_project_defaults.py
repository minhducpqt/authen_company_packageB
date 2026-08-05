# utils/company_project_defaults.py
"""Mirror Service A — mặc định hình thức đấu khi tạo dự án mới."""
from __future__ import annotations

COMPANY_DEFAULT_REGISTRATION_MODE = {
    "kinhdo": "NORMAL",
    "kido": "NORMAL",
    "vnt": "GROUP_AUCTION",
}

REGISTRATION_MODE_LABELS = {
    "NORMAL": "Đấu lô (mặc định)",
    "GROUP_AUCTION": "Đấu nhóm",
}

FALLBACK = "NORMAL"


def default_registration_mode_for_company(company_code: str | None) -> str:
    cc = (company_code or "").strip().lower()
    return COMPANY_DEFAULT_REGISTRATION_MODE.get(cc, FALLBACK)
