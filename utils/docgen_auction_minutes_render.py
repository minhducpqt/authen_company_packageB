# utils/docgen_auction_minutes_render.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from starlette.requests import Request

from utils.docgen_contract_render import apply_lot_table, html_to_pdf_bytes, inject_preview_bridge
from utils.docgen_regulations_render import _amount_words_vnd
from utils.templates import templates

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

DEFAULT_BIDDERS_NOTE = (
    "Danh sách người tham gia đấu giá được đính kèm cùng biên bản này."
)


def _slug(s: str) -> str:
    s = (s or "bien-ban").strip()
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.UNICODE)
    return s.strip("-") or "bien-ban"


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


def _fmt_date_vn(raw: Any) -> str:
    dt = _parse_dt(raw)
    if not dt:
        return ""
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year}"


def _fmt_session_clock(raw: Any) -> Tuple[str, str, str]:
    dt = _parse_dt(raw)
    if not dt:
        return "", "", ""
    return str(dt.hour), f"{dt.minute:02d}", _fmt_date_vn(dt)


def _normalize_guests(raw: Any) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, dict):
            row = {
                "full_name": str(item.get("full_name") or "").strip(),
                "title": str(item.get("title") or "").strip(),
                "workplace": str(item.get("workplace") or "").strip(),
            }
            if row["full_name"] or row["title"] or row["workplace"]:
                out.append(row)
        elif isinstance(item, str) and item.strip():
            out.append({"full_name": item.strip(), "title": "", "workplace": ""})
    return out


def _company_name_from_ctx(ctx: Optional[Dict[str, Any]]) -> str:
    if not isinstance(ctx, dict):
        return ""
    co = ctx.get("company") if isinstance(ctx.get("company"), dict) else {}
    return str(co.get("name") or ctx.get("company_name") or "").strip()


def merge_fields_for_render(
    fields: Optional[Dict[str, Any]],
    *,
    ctx: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    src = dict(fields or {})
    minutes = dict(src.get("minutes") or {})
    out = dict(minutes)

    if not out.get("form_code"):
        out["form_code"] = "TP-ĐGTS-18"

    if out.get("contract_date"):
        out["contract_date"] = _fmt_date_vn(out["contract_date"]) or out["contract_date"]

    h, m, d = _fmt_session_clock(out.get("session_start_at"))
    if h:
        out["session_time_h"] = h
    if m:
        out["session_time_m"] = m
    if d:
        out["session_date"] = d

    eh, em, ed = _fmt_session_clock(out.get("session_end_at"))
    if eh:
        out["end_time_h"] = eh
    if em:
        out["end_time_m"] = em
    if ed:
        out["end_date"] = ed

    project = (ctx or {}).get("project") if isinstance(ctx, dict) else {}
    if project and not (out.get("asset_description") or "").strip():
        out["asset_description"] = (
            project.get("name") or project.get("project_code") or ""
        ).strip()

    if not (out.get("organizer") or "").strip():
        cname = _company_name_from_ctx(ctx)
        if cname:
            out["organizer"] = cname

    out["guests"] = _normalize_guests(out.get("guests"))

    if not (out.get("bidders_note") or "").strip():
        out["bidders_note"] = DEFAULT_BIDDERS_NOTE

    if not (out.get("auctioneer_name") or "").strip() and (out.get("auctioneer") or "").strip():
        out["auctioneer_name"] = str(out.get("auctioneer") or "").strip()

    return out


def _merge_minutes_values(
    flat: Dict[str, Any],
    ctx: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Gộp defaults từ context (party_a, party_b...) cho template."""
    values = dict((ctx or {}).get("defaults") or {})
    if isinstance(ctx, dict):
        co = ctx.get("company") if isinstance(ctx.get("company"), dict) else {}
        if co.get("name") and not values.get("party_b_name"):
            values["party_b_name"] = co.get("name")
    for key, val in (flat or {}).items():
        if val is not None and str(val).strip():
            values[key] = val
    return values


def _prepare_project_lots(
    fields: Optional[Dict[str, Any]],
    ctx: Optional[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], bool, Dict[str, float]]:
    lots, show_map = apply_lot_table(fields or {}, (ctx or {}).get("lots") or [])
    total_area = sum(float(l.get("area") or 0) for l in lots)
    total_start = sum(float(l.get("starting_price_vnd") or 0) for l in lots)
    total_deposit = sum(float(l.get("deposit_vnd") or 0) for l in lots)
    totals = {
        "area": total_area,
        "starting_price_vnd": total_start,
        "deposit_vnd": total_deposit,
    }
    return lots, show_map, totals


def _progression_from_minutes(minutes: Dict[str, Any]) -> Dict[str, Any]:
    prog = minutes.get("progression")
    if isinstance(prog, dict) and prog:
        out = dict(prog)
        if not out.get("failed_lots_pre_session") and not out.get("failed_lots_in_session"):
            legacy = list(out.get("failed_lots") or minutes.get("failed_lots") or [])
            if legacy:
                out.setdefault("failed_lots_in_session", legacy)
        return out
    return {
        "failed_lots": list(minutes.get("failed_lots") or []),
        "failed_lots_pre_session": list((prog or {}).get("failed_lots_pre_session") or []),
        "failed_lots_in_session": list((prog or {}).get("failed_lots_in_session") or []),
        "won_lots": list(minutes.get("won_lots") or []),
        "eligible_lots": list((prog or {}).get("eligible_lots") or []),
        "round_sections": [],
        "summary": {},
        "price_labels": {},
    }


def _lots_from_progression(prog: Dict[str, Any]) -> Tuple[List[Any], List[Any]]:
    failed = prog.get("failed_lots")
    won = prog.get("won_lots")
    return (
        list(failed) if isinstance(failed, list) else [],
        list(won) if isinstance(won, list) else [],
    )


def download_filename(inst: Dict[str, Any], ext: str = "html") -> str:
    title = (inst.get("title") or "bien-ban-dau-gia").strip()
    code = (inst.get("project_code") or "").strip()
    base = _slug(code or title)
    iid = inst.get("id") or "draft"
    return f"{base}-bien-ban-{iid}.{ext}"


def attachment_content_disposition(filename: str) -> str:
    from urllib.parse import quote

    safe = quote(filename)
    return f"attachment; filename=\"{filename}\"; filename*=UTF-8''{safe}"


def render_auction_minutes_html(
    request: Request,
    *,
    template_path: str,
    fields: Dict[str, Any],
    ctx: Optional[Dict[str, Any]] = None,
    instance: Optional[Dict[str, Any]] = None,
    for_download: bool = False,
    for_preview: bool = False,
) -> str:
    minutes = dict((fields or {}).get("minutes") or {})
    flat = merge_fields_for_render(fields, ctx=ctx)
    progression = _progression_from_minutes(minutes)
    failed_lots, won_lots = _lots_from_progression(progression)
    price_labels = progression.get("price_labels") or {}
    project = (ctx or {}).get("project") if isinstance(ctx, dict) else {}
    company = (ctx or {}).get("company") if isinstance(ctx, dict) else {}
    defaults = (ctx or {}).get("defaults") if isinstance(ctx, dict) else {}
    ward = (ctx or {}).get("ward") if isinstance(ctx, dict) else {}
    project_lots, show_map_parcel, lot_totals = _prepare_project_lots(fields, ctx)
    values = _merge_minutes_values(flat, ctx)
    if lot_totals.get("starting_price_vnd", 0) > 0:
        values.setdefault(
            "total_starting_price_words",
            _amount_words_vnd(lot_totals["starting_price_vnd"]),
        )

    html = templates.get_template(template_path).render(
        request=request,
        title=(instance or {}).get("title") or "Biên bản đấu giá",
        document_no=(instance or {}).get("document_no") or "",
        for_download=for_download,
        for_preview=for_preview,
        fields=flat,
        values=values,
        defaults=defaults or {},
        company=company or {},
        ward=ward or {},
        progression=progression,
        failed_lots=failed_lots,
        won_lots=won_lots,
        round_sections=progression.get("round_sections") or [],
        project_lots=project_lots,
        show_map_parcel=show_map_parcel,
        lot_totals=lot_totals,
        session={},
        project=project or {},
        price_labels=price_labels,
        session_id=minutes.get("session_id"),
        project_id=(instance or {}).get("project_id"),
        error=None,
    )
    if for_preview:
        html = inject_preview_bridge(html)
    return html


__all__ = [
    "DEFAULT_BIDDERS_NOTE",
    "attachment_content_disposition",
    "download_filename",
    "html_to_pdf_bytes",
    "merge_fields_for_render",
    "render_auction_minutes_html",
]
