# routers/forms.py — Biểu mẫu hỗ trợ in ấn (mọi user đăng nhập)
"""
Tầng:
  1) GET /bieu-mau                         — chọn loại biểu mẫu
  2) GET /bieu-mau/phieu-tra-gia           — danh sách mẫu trong loại
  3) GET /bieu-mau/phieu-tra-gia/dau-thuong — studio (trái config · phải preview)
  4) POST /bieu-mau/phieu-tra-gia/dau-thuong/preview — render đúng bid_sheet.html
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from utils.auth import fetch_me, get_access_token
from utils.bid_ticket_qr import qr_png_data_uri
from utils.document_templates.registry import DocKind, company_code_from_me, resolve_template
from utils.templates import templates

router = APIRouter(tags=["forms"], prefix="/bieu-mau")

_DEMO_QR_PAYLOAD = "VNTECHX-SUPPORT-DEMO-BID-SHEET-NOT-VALID"

# Catalog tầng 1
FORM_TYPES = [
    {
        "id": "phieu-tra-gia",
        "name": "Phiếu trả giá",
        "description": "Mẫu in phiếu trả giá hỗ trợ công ty (demo / đào tạo / in thử).",
        "icon": "ri-file-list-3-line",
        "href": "/bieu-mau/phieu-tra-gia",
        "enabled": True,
    },
]

# Catalog tầng 2 trong “Phiếu trả giá”
BID_SHEET_TEMPLATES = [
    {
        "id": "dau-thuong",
        "name": "Phiếu trả giá — Đấu thường",
        "description": "Đúng layout phiếu trả giá NORMAL hiện hành (template hệ thống in production).",
        "icon": "ri-auction-line",
        "href": "/bieu-mau/phieu-tra-gia/dau-thuong",
        "enabled": True,
    },
]


def _num_or_none(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "").replace(",", "")
    if not s:
        return None
    # 15.000.000 (dấu chấm phân cách nghìn)
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
    """Ghép dict ticket khớp schema template bid_sheet (đấu thường)."""
    customer_id = _int_or_none(data.get("customer_id")) or 0
    stt_raw = str(data.get("stt") or "").strip()
    stt_padded = _pad_stt(stt_raw)

    session_id = _int_or_none(data.get("session_id"))
    is_multi_round = _bool_form(data.get("is_multi_round"), False)
    # Nếu bật hiện vòng: cần session_id + is_multi_round + round_no
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

    t: Dict[str, Any] = {
        "ticket_mode": "NORMAL",  # đấu thường — không BLANK/group
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
    return t


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


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def forms_catalog(request: Request):
    """Tầng 1 — chọn loại biểu mẫu."""
    return templates.TemplateResponse(
        "pages/forms/catalog.html",
        {
            "request": request,
            "title": "Biểu mẫu",
            "form_types": FORM_TYPES,
        },
    )


@router.get("/phieu-tra-gia", response_class=HTMLResponse)
async def bid_sheet_template_list(request: Request):
    """Tầng 2 — danh sách mẫu thuộc phiếu trả giá."""
    return templates.TemplateResponse(
        "pages/forms/bid_sheet_list.html",
        {
            "request": request,
            "title": "Phiếu trả giá — danh sách mẫu",
            "templates_list": BID_SHEET_TEMPLATES,
        },
    )


@router.get("/phieu-tra-gia/dau-thuong", response_class=HTMLResponse)
async def bid_sheet_normal_studio(request: Request):
    """Tầng 3 — studio config + preview (đấu thường)."""
    return templates.TemplateResponse(
        "pages/forms/bid_sheet_normal_studio.html",
        {
            "request": request,
            "title": "Mẫu phiếu trả giá — Đấu thường",
            "defaults": DEFAULT_NORMAL_FORM,
            "preview_url": "/bieu-mau/phieu-tra-gia/dau-thuong/preview",
        },
    )


@router.post("/phieu-tra-gia/dau-thuong/preview", response_class=HTMLResponse)
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
    """
    Render đúng template phiếu trả giá production (default / theo company_code user).
    QR = demo cố định. auto_print=False để không bật print ngay trong iframe.
    """
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
