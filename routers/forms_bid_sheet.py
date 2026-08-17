# routers/forms_bid_sheet.py — Studio preview phiếu trả giá (add-on, không đụng /bid-tickets production)
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from utils.auth import fetch_me, get_access_token
from utils.bid_ticket_qr import qr_png_data_uri
from utils.document_templates.registry import DocKind, company_code_from_me, resolve_template
from utils.forms_catalog.catalog import (
    BID_SHEET_VARIANTS,
    enrich_items_with_template_source,
    get_form_item,
    get_phase,
    template_source_for_item,
)
from utils.templates import templates

router = APIRouter(tags=["forms-bid-sheet"])

_DEMO_QR_PAYLOAD = "VNTECHX-SUPPORT-DEMO-BID-SHEET-NOT-VALID"


def _num_or_none(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "").replace(",", "")
    if not s:
        return None
    if s.count(".") > 1:
        try:
            return float(s.replace(".", ""))
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _int_or_none(raw: Optional[str]) -> Optional[int]:
    if raw is None or str(raw).strip() == "":
        return None
    n = _num_or_none(raw)
    if n is None:
        return None
    try:
        return int(n)
    except (TypeError, ValueError):
        return None


def _bool_form(raw: Optional[str], default: bool = False) -> bool:
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on", "y")


def _pad_stt(stt: Optional[str]) -> str:
    s = str(stt or "").strip()
    if not s:
        return ""
    if s.isdigit():
        return s.zfill(3) if len(s) < 3 else s
    return s


def build_normal_ticket_from_form(data: Dict[str, Any], *, qr_data_uri: str) -> Dict[str, Any]:
    customer_id = _int_or_none(data.get("customer_id")) or 0
    stt_raw = str(data.get("stt") or "").strip()
    stt_padded = _pad_stt(stt_raw)

    session_id = _int_or_none(data.get("session_id"))
    is_multi_round = _bool_form(data.get("is_multi_round"), False)
    if _bool_form(data.get("show_round"), False):
        is_multi_round = True
        if session_id is None:
            session_id = 1

    round_no = _int_or_none(data.get("round_no"))
    if is_multi_round and round_no is None:
        round_no = 1

    show_price_step = _bool_form(data.get("show_price_step"), True)
    bid_step_rule = (data.get("bid_step_rule") or "LOT_DEFAULT").strip().upper()
    if bid_step_rule not in ("LOT_DEFAULT", "ANY_ABOVE_START"):
        bid_step_rule = "LOT_DEFAULT"

    auction_mode = (data.get("auction_mode") or "PER_LOT").strip().upper()
    if auction_mode not in ("PER_LOT", "PER_SQM"):
        auction_mode = "PER_LOT"

    area = _num_or_none(data.get("area_m2"))
    starting = _num_or_none(data.get("starting_price_vnd"))
    bid_step = _num_or_none(data.get("bid_step_vnd"))
    customer_lot_count = _int_or_none(data.get("customer_lot_count")) or 1

    lot_code = str(data.get("lot_code") or "").strip()
    lot_display = str(data.get("lot_display") or "").strip() or lot_code

    return {
        "ticket_mode": "NORMAL",
        "project_name": str(data.get("project_name") or "").strip(),
        "company_name": str(data.get("company_name") or "").strip(),
        "lot_code": lot_code,
        "lot_display": lot_display,
        "area_m2": area,
        "customer_full_name": str(data.get("customer_full_name") or "").strip(),
        "customer_id": customer_id,
        "stt": stt_raw,
        "stt_padded": stt_padded,
        "cccd": str(data.get("cccd") or "").strip(),
        "address": str(data.get("address") or "").strip(),
        "phone": str(data.get("phone") or "").strip(),
        "starting_price_vnd": starting if starting is not None else 0,
        "bid_step_vnd": bid_step if bid_step is not None else None,
        "bid_step_rule": bid_step_rule,
        "show_price_step": show_price_step,
        "auction_mode": auction_mode,
        "bid_price_unit": auction_mode,
        "customer_lot_count": customer_lot_count,
        "session_id": session_id,
        "round_id": 1,
        "round_no": round_no,
        "is_multi_round": is_multi_round,
        "qr_data_uri": qr_data_uri or None,
    }


DEFAULT_NORMAL_FORM: Dict[str, str] = {
    "company_name": "Công ty Đấu giá ABC",
    "project_name": "Khu đô thị mẫu XYZ",
    "lot_code": "A-01",
    "lot_display": "A-01",
    "area_m2": "120.50",
    "auction_mode": "PER_LOT",
    "starting_price_vnd": "15000000",
    "bid_step_vnd": "100000",
    "bid_step_rule": "LOT_DEFAULT",
    "show_price_step": "1",
    "show_round": "0",
    "is_multi_round": "0",
    "session_id": "",
    "round_no": "1",
    "customer_full_name": "Nguyễn Văn A",
    "customer_id": "1001",
    "stt": "12",
    "cccd": "001234567890",
    "phone": "0901234567",
    "address": "Số 1, phường Mẫu, TP. Hà Nội",
    "customer_lot_count": "1",
}


@router.get("/trong-phien/phieu-tra-gia", response_class=HTMLResponse)
async def bid_sheet_form_detail(request: Request):
    """Trang chi tiết biểu mẫu Phiếu trả giá — liệt kê phiên bản / studio."""
    phase = get_phase("in_session")
    item = get_form_item("in_session", "phieu-tra-gia")
    token = get_access_token(request)
    me = await fetch_me(token) if token else None
    cc = company_code_from_me(me)
    variants = enrich_items_with_template_source(BID_SHEET_VARIANTS, cc)
    tpl_info = template_source_for_item(cc, DocKind.BID_SHEET)
    return templates.TemplateResponse(
        "pages/forms/form_detail.html",
        {
            "request": request,
            "title": "Phiếu trả giá — Trong phiên",
            "phase": phase,
            "item": item,
            "variants": variants,
            "company_code": cc,
            "template_info": tpl_info,
        },
    )


@router.get("/trong-phien/phieu-tra-gia/dau-thuong", response_class=HTMLResponse)
async def bid_sheet_normal_studio(request: Request):
    phase = get_phase("in_session")
    token = get_access_token(request)
    me = await fetch_me(token) if token else None
    cc = company_code_from_me(me)
    tpl_info = template_source_for_item(cc, DocKind.BID_SHEET)
    return templates.TemplateResponse(
        "pages/forms/bid_sheet_normal_studio.html",
        {
            "request": request,
            "title": "Mẫu phiếu trả giá — Đấu thường",
            "phase": phase,
            "defaults": DEFAULT_NORMAL_FORM,
            "preview_url": "/bieu-mau/trong-phien/phieu-tra-gia/dau-thuong/preview",
            "company_code": cc,
            "template_info": tpl_info,
        },
    )


@router.post("/trong-phien/phieu-tra-gia/dau-thuong/preview", response_class=HTMLResponse)
async def bid_sheet_normal_preview(
    request: Request,
    company_name: str = Form(""),
    project_name: str = Form(""),
    lot_code: str = Form(""),
    lot_display: str = Form(""),
    area_m2: str = Form(""),
    auction_mode: str = Form("PER_LOT"),
    starting_price_vnd: str = Form(""),
    bid_step_vnd: str = Form(""),
    bid_step_rule: str = Form("LOT_DEFAULT"),
    show_price_step: str = Form("1"),
    show_round: str = Form("0"),
    is_multi_round: str = Form("0"),
    session_id: str = Form(""),
    round_no: str = Form("1"),
    customer_full_name: str = Form(""),
    customer_id: str = Form(""),
    stt: str = Form(""),
    cccd: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    customer_lot_count: str = Form("1"),
):
    token = get_access_token(request)
    me = await fetch_me(token) if token else None
    tpl = resolve_template(company_code_from_me(me), DocKind.BID_SHEET)

    form_data = {
        "company_name": company_name,
        "project_name": project_name,
        "lot_code": lot_code,
        "lot_display": lot_display,
        "area_m2": area_m2,
        "auction_mode": auction_mode,
        "starting_price_vnd": starting_price_vnd,
        "bid_step_vnd": bid_step_vnd,
        "bid_step_rule": bid_step_rule,
        "show_price_step": show_price_step,
        "show_round": show_round,
        "is_multi_round": is_multi_round,
        "session_id": session_id,
        "round_no": round_no,
        "customer_full_name": customer_full_name,
        "customer_id": customer_id,
        "stt": stt,
        "cccd": cccd,
        "phone": phone,
        "address": address,
        "customer_lot_count": customer_lot_count,
    }
    qr = qr_png_data_uri(_DEMO_QR_PAYLOAD, box_size=6) or ""
    ticket = build_normal_ticket_from_form(form_data, qr_data_uri=qr)

    return templates.TemplateResponse(
        tpl,
        {
            "request": request,
            "tickets": [ticket],
            "auto_print": False,
        },
    )


@router.post("/phieu-tra-gia/dau-thuong/preview", response_class=HTMLResponse, include_in_schema=False)
async def bid_sheet_normal_preview_legacy(
    request: Request,
    company_name: str = Form(""),
    project_name: str = Form(""),
    lot_code: str = Form(""),
    lot_display: str = Form(""),
    area_m2: str = Form(""),
    auction_mode: str = Form("PER_LOT"),
    starting_price_vnd: str = Form(""),
    bid_step_vnd: str = Form(""),
    bid_step_rule: str = Form("LOT_DEFAULT"),
    show_price_step: str = Form("1"),
    show_round: str = Form("0"),
    is_multi_round: str = Form("0"),
    session_id: str = Form(""),
    round_no: str = Form("1"),
    customer_full_name: str = Form(""),
    customer_id: str = Form(""),
    stt: str = Form(""),
    cccd: str = Form(""),
    phone: str = Form(""),
    address: str = Form(""),
    customer_lot_count: str = Form("1"),
):
    return await bid_sheet_normal_preview(
        request,
        company_name=company_name,
        project_name=project_name,
        lot_code=lot_code,
        lot_display=lot_display,
        area_m2=area_m2,
        auction_mode=auction_mode,
        starting_price_vnd=starting_price_vnd,
        bid_step_vnd=bid_step_vnd,
        bid_step_rule=bid_step_rule,
        show_price_step=show_price_step,
        show_round=show_round,
        is_multi_round=is_multi_round,
        session_id=session_id,
        round_no=round_no,
        customer_full_name=customer_full_name,
        customer_id=customer_id,
        stt=stt,
        cccd=cccd,
        phone=phone,
        address=address,
        customer_lot_count=customer_lot_count,
    )
