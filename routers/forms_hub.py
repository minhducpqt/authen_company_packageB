# routers/forms_hub.py — Hub biểu mẫu theo giai đoạn phiên (add-on, tách production print)
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.auth import fetch_me, get_access_token
from utils.document_templates.registry import company_code_from_me
from utils.forms_catalog.catalog import (
    enrich_items_with_template_source,
    enrich_phases_with_counts,
    get_form_item,
    get_phase,
    list_form_items,
    list_config_items,
    template_source_for_item,
)
from utils.templates import templates

router = APIRouter(tags=["forms-hub"])


async def _company_ctx(request: Request) -> dict:
    token = get_access_token(request)
    me = await fetch_me(token) if token else None
    cc = company_code_from_me(me)
    return {"me": me, "company_code": cc}


def _phase_list_ctx(phase_id: str, company_code: str) -> dict:
    phase = get_phase(phase_id)
    items = enrich_items_with_template_source(list_form_items(phase_id), company_code)
    return {
        "phase": phase,
        "items": items,
        "item_count": len(items),
        "company_code": company_code,
    }


@router.get("/", response_class=HTMLResponse)
async def forms_phase_hub(request: Request):
    ctx = await _company_ctx(request)
    return templates.TemplateResponse(
        "pages/forms/phase_hub.html",
        {
            "request": request,
            "title": "Biểu mẫu",
            "phases": enrich_phases_with_counts(),
            "config_items": list_config_items(),
            "company_code": ctx["company_code"],
        },
    )


@router.get("/truoc-phien", response_class=HTMLResponse)
async def forms_pre_session(request: Request):
    ctx = await _company_ctx(request)
    data = _phase_list_ctx("pre_session", ctx["company_code"])
    return templates.TemplateResponse(
        "pages/forms/phase_items.html",
        {"request": request, "title": "Trước phiên — Biểu mẫu", **data},
    )


@router.get("/trong-phien", response_class=HTMLResponse)
async def forms_in_session(request: Request):
    ctx = await _company_ctx(request)
    data = _phase_list_ctx("in_session", ctx["company_code"])
    return templates.TemplateResponse(
        "pages/forms/phase_items.html",
        {"request": request, "title": "Trong phiên — Biểu mẫu", **data},
    )


@router.get("/sau-phien", response_class=HTMLResponse)
async def forms_post_session(request: Request):
    ctx = await _company_ctx(request)
    data = _phase_list_ctx("post_session", ctx["company_code"])
    return templates.TemplateResponse(
        "pages/forms/phase_items.html",
        {"request": request, "title": "Sau phiên — Biểu mẫu", **data},
    )


@router.get("/phieu-tra-gia")
async def legacy_bid_sheet_list():
    return RedirectResponse(url="/bieu-mau/trong-phien/phieu-tra-gia", status_code=301)


@router.get("/phieu-tra-gia/dau-thuong")
async def legacy_bid_sheet_studio():
    return RedirectResponse(
        url="/bieu-mau/trong-phien/phieu-tra-gia/dau-thuong", status_code=301
    )
