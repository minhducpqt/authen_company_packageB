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

FORM_CONFIG_ITEMS: List[Dict[str, Any]] = [
    {
        "id": "dia-phuong",
        "slug": "dia-phuong",
        "name": "Địa phương",
        "description": "Cấu hình mặc định Bên A, đại diện và địa điểm theo xã/phường.",
        "icon": "ri-map-pin-line",
        "href": "/bieu-mau/cau-hinh/dia-phuong",
    },
]

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
            "description": "Hợp đồng dịch vụ đấu giá tài sản và các tài liệu liên quan.",
            "icon": "ri-file-text-line",
            "href": "/bieu-mau/truoc-phien/hop-dong",
            "enabled": True,
            "status": "active",
            "doc_kind": DocKind.SERVICE_CONTRACT,
            "template_key": "service_contract_v1",
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

# Quy chế: sinh từ HĐ đã chốt, quản lý tại «Theo dự án» — không hiện trong hub Trước phiên.
# Thứ tự luồng giấy tờ trên màn «Theo dự án» (trên → dưới).
_PROJECT_WORKFLOW: List[tuple[str, str]] = [
    ("truoc-phien", "hop-dong"),
    ("truoc-phien", "quy-che"),
]

_WORKFLOW_INSTANCE_KEYS = frozenset(_PROJECT_WORKFLOW)

_PROJECT_DOC_TYPES: Dict[str, Dict[str, Any]] = {
    "quy-che": {
        "id": "quy-che",
        "slug": "quy-che",
        "phase_id": "pre_session",
        "name": "Quy chế",
        "description": "Quy chế cuộc đấu giá (M5.1) — sinh từ hợp đồng đã chốt.",
        "icon": "ri-book-2-line",
        "doc_kind": DocKind.AUCTION_REGULATIONS,
        "template_key": "auction_regulations_v1",
    },
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
    meta = _PROJECT_DOC_TYPES.get(item_slug)
    if meta and meta.get("phase_id") == phase_id:
        return dict(meta)
    return None


def get_project_doc_type(category_slug: str) -> Optional[Dict[str, Any]]:
    return dict(_PROJECT_DOC_TYPES[category_slug]) if category_slug in _PROJECT_DOC_TYPES else None


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


def list_config_items() -> List[Dict[str, Any]]:
    return [dict(x) for x in FORM_CONFIG_ITEMS]


def get_project_forms_hub() -> Dict[str, Any]:
    return {
        "id": "theo-du-an",
        "name": "Các biểu mẫu theo dự án",
        "description": "Tra cứu biểu mẫu theo dự án: luồng hợp đồng → quy chế và các giấy tờ khác theo giai đoạn phiên.",
        "icon": "ri-folder-chart-line",
        "color": "indigo",
        "href": "/bieu-mau/theo-du-an",
        "count_label": "Tra cứu theo dự án",
    }


def resolve_instance_type_label(phase_slug: str, category_slug: str) -> str:
    item = get_form_item_by_phase_slug(phase_slug, category_slug)
    if item:
        return item.get("name") or category_slug
    meta = get_project_doc_type(category_slug)
    if meta:
        return meta.get("name") or category_slug
    return category_slug.replace("-", " ").title()


def _workflow_doc_meta(phase_slug: str, category_slug: str) -> Dict[str, Any]:
    item = get_form_item_by_phase_slug(phase_slug, category_slug)
    if item:
        return {
            "name": item.get("name") or category_slug,
            "description": item.get("description") or "",
            "icon": item.get("icon") or "ri-file-line",
        }
    meta = get_project_doc_type(category_slug)
    if meta:
        return {
            "name": meta.get("name") or category_slug,
            "description": meta.get("description") or "",
            "icon": meta.get("icon") or "ri-file-line",
        }
    return {
        "name": category_slug.replace("-", " ").title(),
        "description": "",
        "icon": "ri-file-line",
    }


def project_docgen_actions(
    instances: List[Dict[str, Any]],
    *,
    project_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Trạng thái HĐ / quy chế của dự án cho màn «Theo dự án»."""
    contract: Optional[Dict[str, Any]] = None
    regulations: Optional[Dict[str, Any]] = None
    for inst in instances or []:
        if (inst.get("phase_slug"), inst.get("category_slug")) == ("truoc-phien", "hop-dong"):
            contract = inst
        elif (inst.get("phase_slug"), inst.get("category_slug")) == ("truoc-phien", "quy-che"):
            regulations = inst
    contract_final = bool(contract and contract.get("status") == "FINAL")
    pid = int(project_id) if project_id else None
    spawn_href = (
        f"/bieu-mau/theo-du-an/sinh-quy-che?project_id={pid}"
        if pid and contract_final and not regulations
        else None
    )
    create_contract_href = (
        f"/bieu-mau/truoc-phien/hop-dong/tao?project_id={pid}"
        if pid and not contract
        else None
    )
    return {
        "contract": contract,
        "contract_id": contract.get("id") if contract else None,
        "contract_final": contract_final,
        "regulations": regulations,
        "regulations_id": regulations.get("id") if regulations else None,
        "can_spawn_regulations": contract_final and not regulations,
        "spawn_regulations_href": spawn_href,
        "can_create_contract": bool(pid and not contract),
        "create_contract_href": create_contract_href,
    }


def project_workflow_steps(
    instances: List[Dict[str, Any]],
    *,
    project_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Các bước luồng giấy tờ theo dự án (HĐ → quy chế → …)."""
    actions = project_docgen_actions(instances, project_id=project_id)
    contract = actions.get("contract")
    regulations = actions.get("regulations")
    steps: List[Dict[str, Any]] = []

    meta = _workflow_doc_meta("truoc-phien", "hop-dong")
    if contract:
        row = dict(contract)
        row["type_label"] = resolve_instance_type_label("truoc-phien", "hop-dong")
        row["open_href"] = resolve_instance_href(row)
        steps.append(
            {
                **meta,
                "slug": "hop-dong",
                "instance": row,
                "status": "ready",
                "desc": "Hợp đồng dịch vụ đấu giá của dự án.",
                "primary_href": row["open_href"],
                "primary_label": "Mở hợp đồng",
                "primary_icon": "ri-file-text-line",
            }
        )
    else:
        steps.append(
            {
                **meta,
                "slug": "hop-dong",
                "instance": None,
                "status": "missing",
                "desc": "Tạo hợp đồng dịch vụ đấu giá cho dự án (một hợp đồng / dự án).",
                "primary_href": actions.get("create_contract_href"),
                "primary_label": "Tạo hợp đồng",
                "primary_icon": "ri-add-line",
            }
        )

    meta = _workflow_doc_meta("truoc-phien", "quy-che")
    if regulations:
        row = dict(regulations)
        row["type_label"] = resolve_instance_type_label("truoc-phien", "quy-che")
        row["open_href"] = resolve_instance_href(row)
        steps.append(
            {
                **meta,
                "slug": "quy-che",
                "instance": row,
                "status": "ready",
                "desc": "Quy chế đấu giá đã sinh từ hợp đồng đã chốt.",
                "primary_href": row["open_href"],
                "primary_label": "Mở quy chế",
                "primary_icon": "ri-book-2-line",
            }
        )
    elif actions.get("can_spawn_regulations"):
        steps.append(
            {
                **meta,
                "slug": "quy-che",
                "instance": None,
                "status": "action",
                "desc": "Hợp đồng đã chốt — sinh quy chế từ dữ liệu hợp đồng (một quy chế / dự án).",
                "primary_href": actions.get("spawn_regulations_href"),
                "primary_label": "Sinh quy chế",
                "primary_icon": "ri-add-line",
            }
        )
    elif contract and not actions.get("contract_final"):
        steps.append(
            {
                **meta,
                "slug": "quy-che",
                "instance": None,
                "status": "blocked",
                "desc": "Cần chốt hợp đồng trước khi sinh quy chế.",
                "secondary_href": f"/bieu-mau/truoc-phien/hop-dong/{actions['contract_id']}",
                "secondary_label": "Mở hợp đồng",
            }
        )
    else:
        steps.append(
            {
                **meta,
                "slug": "quy-che",
                "instance": None,
                "status": "blocked",
                "desc": "Tạo và chốt hợp đồng trước, sau đó sinh quy chế tại đây.",
            }
        )

    return steps


def resolve_instance_href(inst: Dict[str, Any]) -> str:
    phase_slug = inst.get("phase_slug") or ""
    category_slug = inst.get("category_slug") or ""
    iid = inst.get("id")
    if phase_slug == "truoc-phien" and category_slug == "hop-dong" and iid:
        return f"/bieu-mau/truoc-phien/hop-dong/{iid}"
    if phase_slug == "truoc-phien" and category_slug == "quy-che" and iid:
        return f"/bieu-mau/truoc-phien/quy-che/{iid}"
    item = get_form_item_by_phase_slug(phase_slug, category_slug)
    if item and item.get("href"):
        return str(item["href"])
    phase = get_phase_by_slug(phase_slug)
    if phase:
        return str(phase.get("href") or "/bieu-mau")
    return "/bieu-mau"


def enrich_instances_for_project_view(instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for inst in instances:
        row = dict(inst)
        row["type_label"] = resolve_instance_type_label(
            row.get("phase_slug") or "", row.get("category_slug") or ""
        )
        row["open_href"] = resolve_instance_href(row)
        out.append(row)
    return out


def group_instances_by_phase(instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched = enrich_instances_for_project_view(instances)
    buckets: Dict[str, List[Dict[str, Any]]] = {p["slug"]: [] for p in FORM_PHASES}
    for inst in enriched:
        key = (inst.get("phase_slug") or "", inst.get("category_slug") or "")
        if key in _WORKFLOW_INSTANCE_KEYS:
            continue
        slug = inst.get("phase_slug") or ""
        if slug in buckets:
            buckets[slug].append(inst)
    groups = []
    for phase in FORM_PHASES:
        items = buckets.get(phase["slug"], [])
        groups.append({"phase": dict(phase), "forms": items, "count": len(items)})
    return groups
