# utils/project_auction_type.py
"""Phân loại dự án hiển thị trên UI: đấu lô / đấu nhóm mù / đấu nhóm chọn lô."""
from __future__ import annotations

from typing import Any, Dict, Optional

KIND_NORMAL = "NORMAL"
KIND_GROUP_BLIND = "GROUP_BLIND"
KIND_GROUP_PRE_SESSION = "GROUP_PRE_SESSION"

AUCTION_TYPE_LABELS = {
    KIND_NORMAL: "Đấu thường",
    KIND_GROUP_BLIND: "Đấu nhóm (khách chọn lô trong phiên)",
    KIND_GROUP_PRE_SESSION: "Đấu nhóm (khách chọn lô trước phiên)",
}


def _group_auction_block(project: Dict[str, Any]) -> Dict[str, Any]:
    ga = project.get("group_auction")
    if isinstance(ga, dict):
        return ga
    extras = project.get("extras")
    if isinstance(extras, dict):
        inner = extras.get("group_auction")
        if isinstance(inner, dict):
            return inner
    return {}


def project_auction_type_meta(project: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(project, dict):
        return {
            "registration_mode": "NORMAL",
            "lot_policy": None,
            "auction_type_kind": KIND_NORMAL,
            "auction_type_label": AUCTION_TYPE_LABELS[KIND_NORMAL],
        }

    mode = (project.get("registration_mode") or "NORMAL").strip().upper()
    ga = _group_auction_block(project)
    lot_policy = (ga.get("lot_policy") or "IN_SESSION_R1").strip().upper()

    if mode != "GROUP_AUCTION":
        kind = KIND_NORMAL
    elif lot_policy == "PRE_SESSION":
        kind = KIND_GROUP_PRE_SESSION
    else:
        kind = KIND_GROUP_BLIND

    return {
        "registration_mode": mode,
        "lot_policy": lot_policy if mode == "GROUP_AUCTION" else None,
        "auction_type_kind": kind,
        "auction_type_label": AUCTION_TYPE_LABELS[kind],
    }


def enrich_project_option_row(project: Dict[str, Any]) -> Dict[str, Any]:
    """Chuẩn hóa 1 dòng option dropdown (code/name/id + meta loại đấu)."""
    pp = project or {}
    code = (pp.get("project_code") or pp.get("code") or "").strip()
    name = (pp.get("name") or pp.get("project_name") or code).strip()
    meta = project_auction_type_meta(pp)
    row: Dict[str, Any] = {
        "project_code": code,
        "name": name,
        **meta,
    }
    pid = pp.get("id", pp.get("project_id"))
    if pid is not None:
        try:
            row["id"] = int(pid)
        except (TypeError, ValueError):
            pass
    status = (pp.get("status") or "").strip()
    if status:
        row["status"] = status
    return row
