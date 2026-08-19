# utils/forms_registration_sample.py — Dữ liệu mẫu studio đơn đăng ký (Biểu mẫu)
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Dict, List, Optional


DEFAULT_LOTS_JSON = """[
  {"lot_code": "A-01", "lot_number": "A-01", "area_m2": 120.5, "starting_price_vnd": 1500000000},
  {"lot_code": "A-02", "lot_number": "A-02", "area_m2": 95.0, "starting_price_vnd": 1200000000},
  {"lot_code": "B-01", "lot_number": "B-01", "area_m2": 200.0, "starting_price_vnd": 2800000000}
]"""

DEFAULT_DEPOSIT_GROUPS_JSON = """[
  {
    "deposit_vnd": 50000000,
    "deposit_vnd_label": "50.000.000",
    "group_name": "Nhóm A",
    "group_label": "Nhóm A — Khu đô thị mẫu",
    "group_total_lots": 12,
    "participating_qty": 2,
    "qty": 2,
    "total_deposit_vnd": 100000000,
    "total_deposit_vnd_label": "100.000.000"
  }
]"""


DEFAULT_REGISTRATION_FORM: Dict[str, str] = {
    "company_name": "Công ty Đấu giá ABC",
    "customer_full_name": "Nguyễn Văn A",
    "cccd": "001234567890",
    "dob": "1990-05-15",
    "phone": "0901234567",
    "email": "nguyenvana@example.com",
    "address": "Số 1, phường Mẫu, quận Trung tâm, TP. Hà Nội",
    "project_code": "DA-MOU",
    "project_name": "Khu đô thị mẫu XYZ",
    "project_description": "Khu đô thị mẫu XYZ — giai đoạn I",
    "project_location": "Phường Mẫu, TP. Hà Nội",
    "refund_bank_name": "Ngân hàng TMCP Ngoại thương Việt Nam",
    "refund_bank_code": "VCB",
    "refund_account_number": "0123456789",
    "refund_account_name": "NGUYEN VAN A",
    "lots_json": DEFAULT_LOTS_JSON,
    "deposit_groups_json": DEFAULT_DEPOSIT_GROUPS_JSON,
}


def _str(v: Any) -> str:
    return str(v or "").strip()


def _parse_json_array(raw: Optional[str], fallback: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    s = (raw or "").strip()
    if not s:
        return fallback
    try:
        data = json.loads(s)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except json.JSONDecodeError:
        pass
    return fallback


def _parse_lots(raw: Optional[str]) -> List[Dict[str, Any]]:
    default = json.loads(DEFAULT_LOTS_JSON)
    lots = _parse_json_array(raw, default)
    out: List[Dict[str, Any]] = []
    for i, lot in enumerate(lots):
        code = _str(lot.get("lot_code") or lot.get("lot_number") or f"L{i + 1}")
        area = lot.get("area_m2")
        try:
            area_f = float(area) if area not in (None, "") else None
        except (TypeError, ValueError):
            area_f = None
        price = lot.get("starting_price_vnd") or lot.get("reserve_price_vnd")
        try:
            price_i = int(float(price)) if price not in (None, "") else None
        except (TypeError, ValueError):
            price_i = None
        out.append(
            {
                "lot_id": int(lot.get("lot_id") or (1000 + i)),
                "lot_code": code,
                "lot_number": _str(lot.get("lot_number") or code),
                "area_m2": area_f,
                "starting_price_vnd": price_i,
                "deposit_amount_vnd": lot.get("deposit_amount_vnd"),
            }
        )
    return out


def _parse_deposit_groups(raw: Optional[str]) -> List[Dict[str, Any]]:
    default = json.loads(DEFAULT_DEPOSIT_GROUPS_JSON)
    groups = _parse_json_array(raw, default)
    out: List[Dict[str, Any]] = []
    for g in groups:
        dep = g.get("deposit_vnd") or 0
        try:
            dep_i = int(float(dep))
        except (TypeError, ValueError):
            dep_i = 0
        qty = g.get("participating_qty") or g.get("qty") or 0
        try:
            qty_i = int(float(qty))
        except (TypeError, ValueError):
            qty_i = 0
        total = g.get("total_deposit_vnd")
        try:
            total_i = int(float(total)) if total not in (None, "") else dep_i * max(qty_i, 1)
        except (TypeError, ValueError):
            total_i = dep_i * max(qty_i, 1)
        out.append(
            {
                "deposit_vnd": dep_i,
                "deposit_vnd_label": _str(g.get("deposit_vnd_label")) or None,
                "group_name": _str(g.get("group_name")) or None,
                "group_label": _str(g.get("group_label")) or None,
                "group_total_lots": int(g.get("group_total_lots") or 0),
                "participating_qty": qty_i,
                "qty": qty_i or None,
                "total_deposit_vnd": total_i,
                "total_deposit_vnd_label": _str(g.get("total_deposit_vnd_label")) or None,
            }
        )
    return out


def _parse_dob(raw: Optional[str]) -> Optional[str]:
    s = _str(raw)
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return s


def build_registration_data_from_form(
    data: Dict[str, Any],
    *,
    registration_mode: str = "NORMAL",
    lot_policy: str = "IN_SESSION_R1",
    company_code: str = "demo",
) -> Dict[str, Any]:
    """Compose payload giống Service A ComposeDocResponse cho render template thật."""
    mode = (registration_mode or "NORMAL").strip().upper()
    policy = (lot_policy or "IN_SESSION_R1").strip().upper()
    cc = _str(company_code).lower() or "demo"

    lots = _parse_lots(data.get("lots_json"))
    deposit_groups = _parse_deposit_groups(data.get("deposit_groups_json"))

    dob_raw = _parse_dob(data.get("dob"))
    dob_val: Optional[date] = None
    if dob_raw and re.match(r"^\d{4}-\d{2}-\d{2}$", dob_raw):
        try:
            dob_val = date.fromisoformat(dob_raw)
        except ValueError:
            dob_val = None

    refund_name = _str(data.get("refund_bank_name"))
    refund_code = _str(data.get("refund_bank_code"))
    refund_acc = _str(data.get("refund_account_number"))
    refund_holder = _str(data.get("refund_account_name"))

    refund_bank = None
    if refund_acc or refund_code:
        refund_bank = {
            "bank_code": refund_code or "VCB",
            "bank_name": refund_name or refund_code or "Ngân hàng",
            "bank_short_name": refund_code or None,
            "account_number": refund_acc or "0000000000",
            "account_name": refund_holder or _str(data.get("customer_full_name")).upper(),
        }

    return {
        "company": {
            "company_code": cc,
            "name": _str(data.get("company_name")) or "Công ty mẫu",
        },
        "customer": {
            "id": 1001,
            "company_code": cc,
            "full_name": _str(data.get("customer_full_name")) or "Nguyễn Văn A",
            "cccd": _str(data.get("cccd")) or "001234567890",
            "dob": dob_val.isoformat() if dob_val else dob_raw,
            "phone": _str(data.get("phone")) or None,
            "email": _str(data.get("email")) or None,
            "address": _str(data.get("address")) or None,
        },
        "project": {
            "id": 1,
            "company_code": cc,
            "project_code": _str(data.get("project_code")) or "DA-MOU",
            "name": _str(data.get("project_name")) or "Dự án mẫu",
            "location": _str(data.get("project_location")) or None,
            "description": _str(data.get("project_description")) or _str(data.get("project_name")),
            "registration_mode": mode,
            "lot_policy": policy if mode == "GROUP_AUCTION" else None,
            "lot_policy_label": "Trước phiên" if policy == "PRE_SESSION" else "Trong phiên",
        },
        "lots": lots if mode != "GROUP_AUCTION" else [],
        "deposit_groups": deposit_groups if mode == "GROUP_AUCTION" else [],
        "registration_mode": mode,
        "refund_bank": refund_bank,
        "meta": {"lot_policy": policy, "studio": True},
    }
