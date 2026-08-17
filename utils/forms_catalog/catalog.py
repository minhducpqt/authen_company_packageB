"""
Catalog biểu mẫu theo giai đoạn phiên đấu giá (add-on, tách khỏi in production).

Resolve mẫu theo công ty: công ty có override → hiển thị riêng; không thì mặc định.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from utils.document_templates.registry import (
    DocKind,
    company_template_path,
    default_template_path,
    resolve_template,
    _template_file_exists,
)

# --- Giai đoạn phiên ---

FORM_PHASES: List[Dict[str, Any]] = [
    {
        "id": "pre_session",
        "slug": "truoc-phien",
        "name": "Trước phiên",
        "description": "Giấy tờ, thủ tục chuẩn bị trước khi mở phiên đấu giá.",
        "icon": "ri-calendar-schedule-line",
        "color": "sky",
        "href": "/bieu-mau/truoc-phien",
    },
    {
        "id": "in_session",
        "slug": "trong-phien",
        "name": "Trong phiên",
        "description": "Biểu mẫu dùng trong lúc vận hành phiên (phiếu trả giá, điểm danh…).",
        "icon": "ri-auction-line",
        "color": "indigo",
        "href": "/bieu-mau/trong-phien",
    },
    {
        "id": "post_session",
        "slug": "sau-phien",
        "name": "Sau phiên",
        "description": "Biên bản, xác nhận và giấy tờ sau khi kết thúc phiên.",
        "icon": "ri-file-check-line",
        "color": "emerald",
        "href": "/bieu-mau/sau-phien",
    },
]

# --- Mục biểu mẫu theo giai đoạn ---

_FORM_ITEMS: Dict[str, List[Dict[str, Any]]] = {
    "pre_session": [
        {
            "id": "hop-dong",
            "slug": "hop-dong",
            "name": "Hợp đồng",
            "description": "Mẫu hợp đồng liên quan đấu giá — đang quy hoạch, chưa triển khai.",
            "icon": "ri-file-text-line",
            "href": "/bieu-mau/truoc-phien/hop-dong",
            "enabled": True,
            "status": "coming_soon",
            "doc_kind": None,
        },
    ],
    "in_session": [
        {
            "id": "phieu-tra-gia",
            "slug": "phieu-tra-gia",
            "name": "Phiếu trả giá",
            "description": "Mẫu in phiếu trả giá (demo / đào tạo / in thử). Production: menu 5.2.",
            "icon": "ri-file-list-3-line",
            "href": "/bieu-mau/trong-phien/phieu-tra-gia",
            "enabled": True,
            "status": "active",
            "doc_kind": DocKind.BID_SHEET,
        },
    ],
    "post_session": [],
}

# --- Chi tiết mẫu con (vd. phiếu trả giá đấu thường) ---

BID_SHEET_VARIANTS: List[Dict[str, Any]] = [
    {
        "id": "dau-thuong",
        "name": "Phiếu trả giá — Đấu thường",
        "description": "Layout phiếu trả giá NORMAL (template hệ thống in production).",
        "icon": "ri-auction-line",
        "href": "/bieu-mau/trong-phien/phieu-tra-gia/dau-thuong",
        "enabled": True,
        "doc_kind": DocKind.BID_SHEET,
    },
]


def get_phase(phase_id: str) -> Optional[Dict[str, Any]]:
    for p in FORM_PHASES:
        if p["id"] == phase_id:
            return dict(p)
    return None


def get_phase_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    for p in FORM_PHASES:
        if p["slug"] == slug:
            return dict(p)
    return None


def list_form_items(phase_id: str) -> List[Dict[str, Any]]:
    return [dict(x) for x in _FORM_ITEMS.get(phase_id, [])]


def enrich_phases_with_counts() -> List[Dict[str, Any]]:
    out = []
    for p in FORM_PHASES:
        row = dict(p)
        n = len(_FORM_ITEMS.get(p["id"], []))
        row["form_count"] = n
        if n == 0:
            row["count_label"] = "Chưa có biểu mẫu"
        elif n == 1:
            row["count_label"] = "1 biểu mẫu"
        else:
            row["count_label"] = f"{n} biểu mẫu"
        out.append(row)
    return out


def get_form_item(phase_id: str, item_slug: str) -> Optional[Dict[str, Any]]:
    for item in _FORM_ITEMS.get(phase_id, []):
        if item.get("slug") == item_slug:
            return dict(item)
    return None


def get_form_item_by_phase_slug(phase_slug: str, item_slug: str) -> Optional[Dict[str, Any]]:
    phase = get_phase_by_slug(phase_slug)
    if not phase:
        return None
    return get_form_item(phase["id"], item_slug)


def template_source_for_item(
    company_code: Optional[str],
    doc_kind: Optional[str],
) -> Dict[str, Any]:
    """
    Trả metadata nguồn mẫu: default vs override công ty.
    """
    cc = (company_code or "").strip().lower()
    if not doc_kind:
        return {
            "source": "none",
            "label": "Chưa gắn mẫu",
            "company_code": cc,
            "template_path": None,
            "has_company_override": False,
        }

    resolved = resolve_template(cc or None, doc_kind)
    default_path = default_template_path(doc_kind)
    company_path = company_template_path(cc, doc_kind) if cc else None
    has_override = bool(cc and company_path and _template_file_exists(company_path))

    if has_override:
        label = f"Mẫu riêng · {cc.upper()}"
        source = "company"
    else:
        label = "Mặc định hệ thống"
        source = "default"

    return {
        "source": source,
        "label": label,
        "company_code": cc,
        "template_path": resolved,
        "default_path": default_path,
        "company_path": company_path,
        "has_company_override": has_override,
    }


def enrich_items_with_template_source(
    items: List[Dict[str, Any]],
    company_code: Optional[str],
) -> List[Dict[str, Any]]:
    out = []
    for item in items:
        row = dict(item)
        row["template_info"] = template_source_for_item(
            company_code, row.get("doc_kind")
        )
        out.append(row)
    return out
