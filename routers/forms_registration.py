# routers/forms_registration.py — Studio preview đơn đăng ký (add-on Biểu mẫu)
from __future__ import annotations

import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from utils.auth import fetch_me, get_access_token
from utils.bid_ticket_qr import qr_png_data_uri
from utils.document_templates.registry import (
    company_code_from_me,
    resolve_registration_template,
)
from utils.forms_catalog.catalog import (
    REGISTRATION_VARIANTS,
    enrich_items_with_template_source,
    get_form_item,
    get_phase,
    get_registration_variant,
    template_source_for_item,
)
from utils.forms_registration_sample import (
    DEFAULT_REGISTRATION_FORM,
    build_registration_data_from_form,
)
from utils.templates import templates

router = APIRouter(tags=["forms-registration"])

_DEMO_QR_PAYLOAD = "VNTECHX-SUPPORT-DEMO-REGISTRATION-NOT-VALID"


def _form_dict(**kwargs: str) -> Dict[str, Any]:
    return {k: v for k, v in kwargs.items()}


@router.get("/truoc-phien/don-dang-ky", response_class=HTMLResponse)
async def registration_form_detail(request: Request):
    phase = get_phase("pre_session")
    item = get_form_item("pre_session", "don-dang-ky")
    token = get_access_token(request)
    me = await fetch_me(token) if token else None
    cc = company_code_from_me(me)
    variants = enrich_items_with_template_source(REGISTRATION_VARIANTS, cc)
    tpl_info = variants[0]["template_info"] if variants else {}
    return templates.TemplateResponse(
        "pages/forms/form_detail.html",
        {
            "request": request,
            "title": "Mẫu đơn đăng ký — Trước phiên",
            "phase": phase,
            "item": item,
            "variants": variants,
            "company_code": cc,
            "template_info": tpl_info,
        },
    )


def _studio_context(
    request: Request,
    *,
    variant_id: str,
    me: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    variant = get_registration_variant(variant_id)
    if not variant:
        raise ValueError(f"Unknown variant: {variant_id}")
    phase = get_phase("pre_session")
    cc = company_code_from_me(me)
    doc_kind = variant.get("doc_kind") or ""
    tpl_info = template_source_for_item(cc, doc_kind)
    slug = variant.get("slug") or variant_id
    return {
        "request": request,
        "title": variant.get("name") or "Mẫu đơn đăng ký",
        "phase": phase,
        "variant": variant,
        "defaults": DEFAULT_REGISTRATION_FORM,
        "preview_url": f"/bieu-mau/truoc-phien/don-dang-ky/{slug}/preview",
        "company_code": cc,
        "template_info": tpl_info,
        "is_group": variant.get("registration_mode") == "GROUP_AUCTION",
    }


@router.get("/truoc-phien/don-dang-ky/{variant_slug}", response_class=HTMLResponse)
async def registration_studio(request: Request, variant_slug: str):
    variant = get_registration_variant(variant_slug)
    if not variant:
        return HTMLResponse("Không tìm thấy phiên bản mẫu.", status_code=404)
    token = get_access_token(request)
    me = await fetch_me(token) if token else None
    ctx = _studio_context(request, variant_id=variant["id"], me=me)
    return templates.TemplateResponse("pages/forms/registration_studio.html", ctx)


@router.post("/truoc-phien/don-dang-ky/{variant_slug}/preview", response_class=HTMLResponse)
async def registration_preview(
    request: Request,
    variant_slug: str,
    company_name: str = Form(""),
    customer_full_name: str = Form(""),
    cccd: str = Form(""),
    dob: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    project_code: str = Form(""),
    project_name: str = Form(""),
    project_description: str = Form(""),
    project_location: str = Form(""),
    refund_bank_name: str = Form(""),
    refund_bank_code: str = Form(""),
    refund_account_number: str = Form(""),
    refund_account_name: str = Form(""),
    lots_json: str = Form(""),
    deposit_groups_json: str = Form(""),
):
    variant = get_registration_variant(variant_slug)
    if not variant:
        return HTMLResponse("Không tìm thấy phiên bản mẫu.", status_code=404)

    token = get_access_token(request)
    me = await fetch_me(token) if token else None
    cc = company_code_from_me(me)

    form_data = _form_dict(
        company_name=company_name,
        customer_full_name=customer_full_name,
        cccd=cccd,
        dob=dob,
        phone=phone,
        email=email,
        address=address,
        project_code=project_code,
        project_name=project_name,
        project_description=project_description,
        project_location=project_location,
        refund_bank_name=refund_bank_name,
        refund_bank_code=refund_bank_code,
        refund_account_number=refund_account_number,
        refund_account_name=refund_account_name,
        lots_json=lots_json,
        deposit_groups_json=deposit_groups_json,
    )

    data = build_registration_data_from_form(
        form_data,
        registration_mode=variant.get("registration_mode") or "NORMAL",
        lot_policy=variant.get("lot_policy") or "IN_SESSION_R1",
        company_code=cc,
    )

    reg_tpl = resolve_registration_template(
        cc,
        data.get("registration_mode"),
        lot_policy=(data.get("project") or {}).get("lot_policy"),
    )

    today = datetime.date.today()
    qr = qr_png_data_uri(_DEMO_QR_PAYLOAD, box_size=6) or ""

    return templates.TemplateResponse(
        reg_tpl,
        {
            "request": request,
            "title": "Đơn đăng ký tham gia đấu giá",
            "data": data,
            "today": today,
            "year": today.year,
            "registration_qr_data_uri": qr or None,
        },
    )
