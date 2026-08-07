# utils/bid_sheet_print.py
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _to_float(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _is_per_sqm_mode(t: Dict[str, Any]) -> bool:
    mode = (t.get("auction_mode") or t.get("bid_price_unit") or "PER_LOT")
    return str(mode).strip().upper() == "PER_SQM"


def _is_session_ticket(t: Dict[str, Any]) -> bool:
    return t.get("session_id") is not None or t.get("round_id") is not None


def _display_deposit_terms(text: Any) -> str:
    """Chuẩn hoá thuật ngữ trên phiếu in: tiền cọc → tiền đặt trước."""
    if text is None or text == "":
        return ""
    s = str(text)
    for old, new in (
        ("Tổng tiền cọc", "Tổng tiền đặt trước"),
        ("tiền cọc", "tiền đặt trước"),
        ("mức cọc", "mức đặt trước"),
        ("Nhóm cọc", "Nhóm đặt trước"),
        ("nhóm cọc", "nhóm đặt trước"),
    ):
        s = s.replace(old, new)
    return s


def normalize_ticket_for_print(t: Dict[str, Any]) -> Dict[str, Any]:
    """
    PER_SQM trước phiên (5.2): starting_price_vnd trong DB = giá cả lô → quy đổi /m².
    PER_SQM trong phiên: API đã trả start_price_vnd theo /m² → giữ nguyên.
    PER_LOT: giữ nguyên giá cả lô.
    """
    out = dict(t)
    if out.get("group_name"):
        out["group_name"] = _display_deposit_terms(out["group_name"])
    if not _is_per_sqm_mode(out):
        return out

    if _is_session_ticket(out):
        return out

    start = _to_float(out.get("starting_price_vnd"))
    area = _to_float(out.get("area_m2"))
    if start is None or area is None or area <= 0:
        return out

    out["starting_price_vnd"] = int(round(start / area))
    return out


def normalize_tickets_for_print(tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [normalize_ticket_for_print(t) for t in tickets]
