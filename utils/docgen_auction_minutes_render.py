# utils/docgen_auction_minutes_render.py
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from starlette.requests import Request

from utils.docgen_contract_render import html_to_pdf_bytes, inject_preview_bridge
from utils.templates import templates

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


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

    guests = out.get("guests")
    if not isinstance(guests, list):
        guests = []
    out["guests"] = [str(g).strip() for g in guests if str(g).strip()]

    return out


def _lots_from_minutes(minutes: Dict[str, Any]) -> Tuple[List[Any], List[Any]]:
    failed = minutes.get("failed_lots")
    won = minutes.get("won_lots")
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
    failed_lots, won_lots = _lots_from_minutes(minutes)
    project = (ctx or {}).get("project") if isinstance(ctx, dict) else {}
    price_labels = (ctx or {}).get("price_labels") if isinstance(ctx, dict) else {}

    html = templates.get_template(template_path).render(
        request=request,
        title=(instance or {}).get("title") or "Biên bản đấu giá",
        for_download=for_download,
        for_preview=for_preview,
        fields=flat,
        failed_lots=failed_lots,
        won_lots=won_lots,
        round_sections=[],
        session={},
        project=project or {},
        price_labels=price_labels or {},
        session_id=minutes.get("session_id"),
        project_id=(instance or {}).get("project_id"),
        error=None,
    )
    if for_preview:
        html = inject_preview_bridge(html)
    return html


__all__ = [
    "attachment_content_disposition",
    "download_filename",
    "html_to_pdf_bytes",
    "merge_fields_for_render",
    "render_auction_minutes_html",
]
