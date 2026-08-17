# utils/docgen_service_fee_land.py — khung phí DV đấu giá QSDĐ (QĐ 1311/QĐ-BTP)
from __future__ import annotations

from typing import Any, Dict, Optional

_LAND_FEE_TIERS: tuple[tuple[int, str], ...] = (
    (1_000_000_000, "13,64"),
    (5_000_000_000, "22,73"),
    (10_000_000_000, "31,82"),
    (50_000_000_000, "40,91"),
    (100_000_000_000, "50"),
)

_FORMULA_TAIL = (
    "1% trên phần chênh lệch giá trị quyền sử dụng đất "
    "theo giá trúng đấu giá với giá khởi điểm"
)


def _base_million_label(total_start_vnd: int) -> Optional[str]:
    total = int(total_start_vnd or 0)
    if total <= 0:
        return None
    for upper, label in _LAND_FEE_TIERS:
        if total <= upper:
            return label
    return "59,09"


def land_service_fee_formula(total_start_vnd: int) -> Optional[str]:
    base = _base_million_label(total_start_vnd)
    if not base:
        return None
    head = "50 triệu đồng" if base == "50" else f"{base} triệu đồng"
    return f"{head} + {_FORMULA_TAIL}"


def compute_land_service_fee(total_start_vnd: int) -> Dict[str, Any]:
    total = int(total_start_vnd or 0)
    return {
        "total_starting_price_vnd": total,
        "base_million_label": _base_million_label(total),
        "formula": land_service_fee_formula(total),
        "vat_note": "Chưa bao gồm thuế VAT",
    }


def total_starting_from_lots(lots: list) -> int:
    return sum(int(lot.get("starting_price_vnd") or 0) for lot in (lots or []))
