# utils/docgen_contract_render.py
from __future__ import annotations

import json
import re
from io import BytesIO
from typing import Any, Dict, Optional
from urllib.parse import quote

from starlette.requests import Request

from utils.docgen_service_fee_land import compute_land_service_fee, total_starting_from_lots
from utils.templates import templates


def _slug(s: str) -> str:
    s = (s or "hop-dong").strip()
    s = re.sub(r"[^\w\-]+", "-", s, flags=re.UNICODE)
    return s.strip("-") or "hop-dong"


_LAND_ARTICLE_DEFAULTS = {
    "land_use_purpose": "Đất ở ……",
    "land_delivery_form": "Nhà nước giao đất có thu tiền sử dụng đất.",
    "land_use_term": "Lâu dài",
    "legal_dossier_ref": "Quyết định số ……",
}

_PAYMENT_TERMS_TAIL = (
    "kể từ ngày bên A đã nhận được kết quả đấu giá, "
    "hóa đơn GTGT và biên bản thanh lý Hợp đồng."
)
_DEFAULT_PAYMENT_DAYS = 20
_VI_DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _vi_read_int(n: int) -> str:
    n = int(n)
    if n < 0:
        return ""
    if n == 0:
        return "không"

    def doc_block(b: int) -> str:
        if not b:
            return ""
        parts: list[str] = []
        tram = b // 100
        chuc = (b % 100) // 10
        don = b % 10
        if tram:
            parts.append(("một" if tram == 1 else _VI_DIGITS[tram]) + " trăm")
        if chuc == 0 and don and tram:
            parts.append("lẻ")
        if chuc == 1:
            parts.append("mười")
        elif chuc > 1:
            parts.append(_VI_DIGITS[chuc] + " mươi")
        if don == 1 and chuc > 1:
            parts.append("mốt")
        elif don == 4 and chuc > 1:
            parts.append("tư")
        elif don == 5 and chuc > 0:
            parts.append("lăm")
        elif don:
            parts.append(_VI_DIGITS[don])
        return " ".join(parts).strip()

    if n < 1000:
        return doc_block(n)
    nghin = n // 1000
    rest = n % 1000
    out = doc_block(nghin) + " nghìn"
    if rest:
        if rest < 100:
            out += " lẻ"
        out += " " + doc_block(rest)
    return out.strip()


def format_payment_terms(days: int) -> str:
    n = max(1, int(days or _DEFAULT_PAYMENT_DAYS))
    words = _vi_read_int(n) or str(n)
    return f"Trong vòng {n} ({words}) ngày {_PAYMENT_TERMS_TAIL}"


def parse_payment_days_from_fees(fees: Dict[str, Any]) -> int:
    if not isinstance(fees, dict):
        return _DEFAULT_PAYMENT_DAYS
    raw_days = fees.get("payment_terms_days")
    if raw_days is not None and str(raw_days).strip():
        try:
            d = int(raw_days)
            if d > 0:
                return d
        except (TypeError, ValueError):
            pass
    text = str(fees.get("payment_terms") or "")
    m = re.search(r"Trong vòng\s+(\d+)", text, re.I) or re.search(r"(\d+)\s*\(", text)
    if m:
        try:
            d = int(m.group(1))
            if d > 0:
                return d
        except (TypeError, ValueError):
            pass
    return _DEFAULT_PAYMENT_DAYS


def normalize_service_fees(fields: Dict[str, Any]) -> None:
    fees = fields.setdefault("service_fees", {})
    if not isinstance(fees, dict):
        fees = {}
        fields["service_fees"] = fees
    days = parse_payment_days_from_fees(fees)
    fees["payment_terms_days"] = days
    fees["payment_terms"] = format_payment_terms(days)


def _company_rep_from_ctx(ctx: Dict[str, Any]) -> tuple[str, str]:
    defs = ctx.get("defaults") or {}
    co = ctx.get("company") or {}
    co_ex = co.get("extras") if isinstance(co.get("extras"), dict) else {}
    rep = (
        (defs.get("party_b_rep_name") or "").strip()
        or (co.get("legal_representative_name") or "").strip()
        or (co_ex.get("legal_representative_name") or "").strip()
        or (co_ex.get("legal_representative") or "").strip()
    )
    title = (
        (defs.get("party_b_rep_title") or "").strip()
        or (co.get("legal_representative_title") or "").strip()
        or (co_ex.get("legal_representative_title") or "").strip()
    )
    return rep, title


def merge_fields_for_render(
    inst: Dict[str, Any],
    ctx: Dict[str, Any],
    fields_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    fields = dict(fields_override if fields_override is not None else (inst.get("fields") or {}))
    contract = fields.setdefault("contract", {})
    if not isinstance(contract, dict):
        contract = {}
        fields["contract"] = contract
    if inst.get("document_no") and not contract.get("document_no"):
        contract["document_no"] = inst["document_no"]
    if inst.get("title") and not contract.get("subtitle"):
        contract["subtitle"] = inst["title"]
    rep, title = _company_rep_from_ctx(ctx)
    if rep and not (contract.get("party_b_rep_name") or "").strip():
        contract["party_b_rep_name"] = rep
    if title and not (contract.get("party_b_rep_title") or "").strip():
        contract["party_b_rep_title"] = title
    for key, default in _LAND_ARTICLE_DEFAULTS.items():
        if not (contract.get(key) or "").strip():
            contract[key] = default
    normalize_service_fees(fields)
    doc_no = contract.get("document_no") or inst.get("document_no")
    if doc_no:
        ctx = dict(ctx)
        ctx.setdefault("values", {})
        ctx["values"]["document_no"] = doc_no
    return fields


def merge_ctx_values_for_render(
    ctx: Dict[str, Any],
    fields: Dict[str, Any],
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge defaults + contract + overrides thành ctx.values phẳng cho template."""
    ctx = dict(ctx)
    values = dict(ctx.get("defaults") or {})
    rep, title = _company_rep_from_ctx(ctx)
    if rep:
        values.setdefault("party_b_rep_name", rep)
    if title:
        values.setdefault("party_b_rep_title", title)
    contract = (fields or {}).get("contract") or {}
    if isinstance(contract, dict):
        for key, val in contract.items():
            if val is not None and str(val).strip():
                values[key] = val
    if overrides:
        for key, val in overrides.items():
            if val is not None and str(val).strip():
                values[key] = val
    ctx["values"] = values
    if overrides is not None:
        ctx["overrides"] = overrides
    return ctx


def apply_lot_table(fields: Dict[str, Any], lots: list) -> tuple[list, bool]:
    """Merge per-lot tờ/thửa from fields.lot_table into ctx.lots for render."""
    lot_table = fields.get("lot_table") or {}
    show = bool(lot_table.get("show_map_parcel"))
    items = lot_table.get("items") or {}
    enriched = []
    for lot in lots or []:
        row = dict(lot)
        if show:
            kid = str(row.get("id") or "")
            kcode = str(row.get("lot_code") or "")
            extra = items.get(kid) or items.get(kcode) or {}
            if isinstance(extra, dict):
                row["map_sheet"] = (extra.get("map_sheet") or "").strip()
                row["parcel_no"] = (extra.get("parcel_no") or "").strip()
            else:
                row["map_sheet"] = ""
                row["parcel_no"] = ""
        enriched.append(row)
    return enriched, show


_PREVIEW_BRIDGE = """
<style>
  .ce-slot { border-radius: 2px; transition: background .15s, box-shadow .15s; }
  .ce-slot.ce-missing { background: #fef08a !important; box-shadow: inset 0 0 0 1px #facc15; }
  .ce-slot.ce-active { background: #bfdbfe !important; box-shadow: inset 0 0 0 2px #2563eb; }
  .ce-slot.ce-active.ce-missing { background: #bfdbfe !important; box-shadow: inset 0 0 0 2px #2563eb, inset 0 -3px 0 #facc15; }
  @media print { .ce-slot.ce-missing, .ce-slot.ce-active { background: transparent !important; box-shadow: none !important; } }
</style>
<script>
(function(){
  var lastScrollField = null;
  function applyHighlight(field, scroll) {
    document.querySelectorAll('.ce-slot').forEach(function(el){ el.classList.remove('ce-active'); });
    if (!field) return;
    var nodes = document.querySelectorAll('.ce-slot[data-ce-field="' + field + '"]');
    nodes.forEach(function(n){ n.classList.add('ce-active'); });
    if (scroll && nodes.length && lastScrollField !== field) {
      lastScrollField = field;
      nodes[0].scrollIntoView({ behavior: 'auto', block: 'nearest', inline: 'nearest' });
    }
    if (!scroll && !field) lastScrollField = null;
  }
  function applyMissing(fields) {
    document.querySelectorAll('.ce-slot').forEach(function(el){ el.classList.remove('ce-missing'); });
    (fields || []).forEach(function(f){
      document.querySelectorAll('.ce-slot[data-ce-field="' + f + '"]').forEach(function(n){
        n.classList.add('ce-missing');
      });
    });
  }
  window.addEventListener('message', function(ev){
    var d = ev.data || {};
    if (d.type === 'ce-highlight') applyHighlight(d.field || null, !!d.scroll);
    if (d.type === 'ce-mark-missing') applyMissing(d.fields || []);
  });
})();
</script>
"""


def inject_preview_bridge(html: str) -> str:
    if "</body>" in html:
        return html.replace("</body>", _PREVIEW_BRIDGE + "</body>", 1)
    return html + _PREVIEW_BRIDGE


async def render_contract_html(
    request: Request,
    *,
    template_path: str,
    ctx: Dict[str, Any],
    fields: Dict[str, Any],
    for_download: bool = False,
) -> str:
    ctx = dict(ctx)
    pa = dict(ctx.get("payment_accounts") or {})
    dep = pa.get("deposit")
    if isinstance(dep, dict):
        pa.setdefault("deposit_account", dep.get("account_number") or "")
        pa.setdefault("deposit_bank", dep.get("bank_name") or "")
        pa.setdefault("deposit_account_name", dep.get("account_name") or "")
    ctx["payment_accounts"] = pa
    lots, show_map_parcel = apply_lot_table(fields, ctx.get("lots") or [])
    ctx["lots"] = lots
    if not ctx.get("service_fee") or not (ctx.get("service_fee") or {}).get("formula"):
        total_start = total_starting_from_lots(lots)
        ctx["service_fee"] = compute_land_service_fee(total_start)
    html = templates.get_template(template_path).render(
        {
            "request": request,
            "ctx": ctx,
            "doc": fields,
            "for_download": for_download,
            "show_map_parcel": show_map_parcel,
        }
    )
    if not for_download:
        html = inject_preview_bridge(html)
    return html


def html_to_pdf_bytes(html: str) -> bytes:
    try:
        from xhtml2pdf import pisa
    except ImportError as exc:
        raise RuntimeError("Thiếu thư viện xhtml2pdf. Chạy: pip install xhtml2pdf") from exc

    buf = BytesIO()
    result = pisa.CreatePDF(html, dest=buf, encoding="utf-8")
    if result.err:
        raise RuntimeError("Không tạo được file PDF")
    return buf.getvalue()



def download_filename(inst: Dict[str, Any], ext: str) -> str:
    no = (inst.get("document_no") or "").strip()
    base = _slug(no) if no else _slug(inst.get("title") or f"hop-dong-{inst.get('id')}")
    return f"{base}.{ext}"


def attachment_content_disposition(filename: str) -> str:
    """RFC 5987 — hỗ trợ tên file tiếng Việt trong header HTTP (latin-1 safe)."""
    name = (filename or "download").replace('"', "'").strip() or "download"
    ascii_name = re.sub(r"[^\x20-\x7E]", "_", name)
    ascii_name = re.sub(r"[^\w.\-]+", "_", ascii_name).strip("._") or "download"
    encoded = quote(name, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def ctx_for_editor(ctx: Dict[str, Any]) -> str:
    """JSON-safe context subset for browser (no datetime objects)."""
    def clean(obj: Any) -> Any:
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [clean(x) for x in obj]
        return str(obj)

    subset = {
        "defaults": clean(ctx.get("defaults") or {}),
        "project": clean(ctx.get("project") or {}),
        "lots": clean(ctx.get("lots") or []),
        "company": clean(ctx.get("company") or {}),
        "locality": clean(ctx.get("locality")) if ctx.get("locality") else None,
        "ward": clean(ctx.get("ward")) if ctx.get("ward") else None,
        "payment_accounts": clean(ctx.get("payment_accounts") or {}),
        "has_locality_profile": bool(ctx.get("locality")),
        "service_fee": clean(ctx.get("service_fee") or {}),
    }
    return json.dumps(subset, ensure_ascii=False)
