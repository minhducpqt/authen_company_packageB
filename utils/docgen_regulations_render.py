# utils/docgen_regulations_render.py
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

from starlette.requests import Request

from utils.bid_ticket_qr import qr_png_data_uri
from utils.customer_portal_urls import customer_portal_link_set
from utils.docgen_contract_render import (
    _vi_read_int,
    apply_lot_table,
    ctx_for_editor,
    download_filename as _download_filename,
    html_to_pdf_bytes,
    inject_preview_bridge,
)
from utils.templates import templates

__all__ = [
    "attachment_content_disposition",
    "ctx_for_editor",
    "download_filename",
    "html_to_pdf_bytes",
    "merge_ctx_values_for_render",
    "merge_fields_for_render",
    "render_regulations_html",
]

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DOSSIER_WINDOW_DAYS = 15
VI_WEEKDAYS = (
    "Chủ nhật",
    "Thứ hai",
    "Thứ ba",
    "Thứ tư",
    "Thứ năm",
    "Thứ sáu",
    "Thứ bảy",
)
_PLANNING_PLACEHOLDER = "Quyết định của Ủy ban nhân dân tỉnh ……"


def _slug(s: str) -> str:
    s = (s or "quy-che").strip()
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.UNICODE)
    return s.strip("-") or "quy-che"


def _parse_dt(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).strip()
        if not text:
            return None
        text = text.replace("Z", "+00:00")
        dt = None
        try:
            dt = datetime.fromisoformat(text[:26])
        except ValueError:
            for fmt in (
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(text[: len(fmt.replace("%f", "000000"))], fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=VN_TZ)
    return dt.astimezone(VN_TZ)


def _iso_local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _fmt_short_period(dt: datetime) -> str:
    return f"{dt.hour:02d}h{dt.minute:02d} ngày {dt.day:02d}/{dt.month:02d}/{dt.year}"


def _fmt_long_period(dt: datetime) -> str:
    return (
        f"{dt.hour} giờ {dt.minute:02d} phút ngày "
        f"{dt.day:02d}/{dt.month:02d}/{dt.year}"
    )


def _vn_weekday(dt: datetime) -> str:
    return VI_WEEKDAYS[(dt.weekday() + 1) % 7]


def _dossier_window_from_application_deadline(
    deadline_at: Any,
) -> Optional[Dict[str, str]]:
    end_vn = _parse_dt(deadline_at)
    if not end_vn:
        return None
    end_date = end_vn.date()
    start_date = end_date - timedelta(days=DOSSIER_WINDOW_DAYS)
    start_dt = datetime(
        start_date.year, start_date.month, start_date.day, 8, 0, tzinfo=VN_TZ
    )
    end_dt = datetime(
        end_date.year, end_date.month, end_date.day, 17, 0, tzinfo=VN_TZ
    )
    return {
        "from_text": _fmt_short_period(start_dt),
        "to_text": _fmt_short_period(end_dt),
        "from_iso": _iso_local(start_dt),
        "to_iso": _iso_local(end_dt),
        "cutoff_text": _fmt_long_period(end_dt),
    }


def _fmt_auction_at_vi(raw: Any) -> Tuple[str, str]:
    dt = _parse_dt(raw)
    if not dt:
        return "", ""
    text = (
        f"Vào {dt.hour} giờ {dt.minute:02d} phút ngày "
        f"{dt.day:02d}/{dt.month:02d}/{dt.year} ({_vn_weekday(dt)})"
    )
    return text, _iso_local(dt)


def _province_label(name: Optional[str]) -> str:
    p = (name or "").strip()
    if not p:
        return ""
    lower = p.lower()
    if lower.startswith(("tỉnh ", "thành phố ", "tp. ")) or "thành phố" in lower:
        return p
    return f"tỉnh {p}"


def _set_if_empty(reg: Dict[str, Any], key: str, val: str) -> None:
    if val and not (reg.get(key) or "").strip():
        reg[key] = val


def _apply_dossier_window(reg: Dict[str, Any], window: Dict[str, str]) -> None:
    for prefix in ("dossier_period", "dossier_resubmit", "deposit_period"):
        _set_if_empty(reg, f"{prefix}_from", window["from_text"])
        _set_if_empty(reg, f"{prefix}_to", window["to_text"])
        _set_if_empty(reg, f"{prefix}_from_iso", window["from_iso"])
        _set_if_empty(reg, f"{prefix}_to_iso", window["to_iso"])
    _set_if_empty(reg, "deposit_cutoff_date", window["cutoff_text"])
    _set_if_empty(reg, "deposit_cutoff_date_iso", window["to_iso"])


def _amount_words_vnd(n: float) -> str:
    val = int(round(float(n or 0)))
    if val <= 0:
        return ""
    parts = []
    ty = val // 1_000_000_000
    rest = val % 1_000_000_000
    if ty:
        parts.append(f"{_vi_read_int(ty)} tỷ")
    trieu = rest // 1_000_000
    rest = rest % 1_000_000
    if trieu:
        parts.append(f"{_vi_read_int(trieu)} triệu")
    nghin = rest // 1_000
    rest = rest % 1_000
    if nghin:
        parts.append(f"{_vi_read_int(nghin)} nghìn")
    if rest:
        parts.append(_vi_read_int(rest))
    return " ".join(p for p in parts if p).strip()


def merge_fields_for_render(
    inst: Dict[str, Any],
    ctx: Dict[str, Any],
    fields_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fields = dict(fields_override if fields_override is not None else (inst.get("fields") or {}))
    reg = fields.setdefault("regulations", {})
    if not isinstance(reg, dict):
        reg = {}
        fields["regulations"] = reg

    if inst.get("document_no") and not (reg.get("document_no") or "").strip():
        reg["document_no"] = inst["document_no"]
    if inst.get("title") and not (reg.get("asset_title") or "").strip():
        reg["asset_title"] = inst["title"]

    proj = ctx.get("project") or {}
    if not (reg.get("asset_title") or "").strip():
        reg["asset_title"] = proj.get("name") or "Quyền sử dụng đất ……"

    auction = proj.get("auction") if isinstance(proj.get("auction"), dict) else {}
    window = _dossier_window_from_application_deadline(
        proj.get("application_deadline_at")
    )
    if window:
        _apply_dossier_window(reg, window)

    if not (reg.get("asset_view_from") or "").strip():
        reg.setdefault("asset_view_from", reg.get("dossier_period_from") or "")
    if not (reg.get("asset_view_to") or "").strip():
        reg.setdefault("asset_view_to", reg.get("dossier_period_to") or "")

    raw_auction = auction.get("auction_at")
    if raw_auction:
        text, iso = _fmt_auction_at_vi(raw_auction)
        _set_if_empty(reg, "auction_at", text)
        _set_if_empty(reg, "auction_at_iso", iso)

    _set_if_empty(reg, "ballot_minutes", "20")
    _set_if_empty(reg, "ballot_minutes_words", "hai mươi")

    planning = (reg.get("planning_decision") or "").strip()
    if not planning or planning == _PLANNING_PLACEHOLDER:
        ward = ctx.get("ward") if isinstance(ctx.get("ward"), dict) else {}
        prov = _province_label(ward.get("province_name"))
        if not prov:
            prov = _province_label(auction.get("province_city"))
        if prov:
            reg["planning_decision"] = f"Quyết định của Ủy ban nhân dân {prov}"

    if not (reg.get("asset_view_location") or "").strip():
        reg.setdefault("asset_view_location", proj.get("location") or "thực địa ……")

    return fields


def merge_ctx_values_for_render(
    ctx: Dict[str, Any],
    fields: Dict[str, Any],
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ctx = dict(ctx)
    values = dict(ctx.get("defaults") or {})
    reg = (fields or {}).get("regulations") or {}
    if isinstance(reg, dict):
        for key, val in reg.items():
            if val is not None and str(val).strip():
                values[key] = val
    if overrides:
        for key, val in overrides.items():
            if val is not None and str(val).strip():
                values[key] = val

    lots = ctx.get("lots") or []
    total_start = sum(float(l.get("starting_price_vnd") or 0) for l in lots)
    if total_start > 0:
        values.setdefault("total_starting_price_words", _amount_words_vnd(total_start))

    ctx["values"] = values
    if overrides is not None:
        ctx["overrides"] = overrides
    return ctx


async def render_regulations_html(
    request: Request,
    *,
    template_path: str,
    ctx: Dict[str, Any],
    fields: Dict[str, Any],
    for_download: bool = False,
) -> str:
    ctx = dict(ctx)
    lots, show_map_parcel = apply_lot_table(fields, ctx.get("lots") or [])
    ctx["lots"] = lots

    company_code = (
        (ctx.get("company") or {}).get("company_code")
        or (ctx.get("project") or {}).get("company_code")
        or ""
    )
    portal_links = customer_portal_link_set(company_code)
    portal_qr_data_uri = None
    if portal_links:
        portal_qr_data_uri = qr_png_data_uri(portal_links["portal_home_url"], box_size=6)

    html = templates.get_template(template_path).render(
        {
            "request": request,
            "ctx": ctx,
            "doc": fields,
            "for_download": for_download,
            "show_map_parcel": show_map_parcel,
            **portal_links,
            "portal_qr_data_uri": portal_qr_data_uri,
        }
    )
    if not for_download:
        html = inject_preview_bridge(html)
    return html


def download_filename(inst: Dict[str, Any], ext: str) -> str:
    no = (inst.get("document_no") or "").strip()
    base = _slug(no) if no else _slug(inst.get("title") or f"quy-che-{inst.get('id')}")
    return f"{base}.{ext}"


def attachment_content_disposition(filename: str) -> str:
    from utils.docgen_contract_render import attachment_content_disposition as _adp

    return _adp(filename)
