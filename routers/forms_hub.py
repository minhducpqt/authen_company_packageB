# routers/forms_hub.py — Hub biểu mẫu theo giai đoạn phiên (add-on, tách production print)
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from services.docgen_v1_client import fetch_projects, list_instances
from utils.auth import fetch_me, get_access_token
from utils.document_templates.registry import company_code_from_me
from utils.forms_catalog.catalog import (
    enrich_items_with_template_source,
    enrich_phases_with_counts,
    get_form_item,
    get_phase,
    get_project_forms_hub,
    group_instances_by_phase,
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
            "project_forms_hub": get_project_forms_hub(),
            "config_items": list_config_items(),
            "company_code": ctx["company_code"],
        },
    )


@router.get("/huong-dan", response_class=HTMLResponse)
async def forms_guide(request: Request):
    return templates.TemplateResponse(
        "pages/forms/guide.html",
        {
            "request": request,
            "title": "Hướng dẫn Biểu mẫu",
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


def _err_msg(exc: Exception) -> str:
    return str(exc)


@router.get("/theo-du-an", response_class=HTMLResponse)
async def forms_by_project(
    request: Request,
    project_id: Optional[int] = Query(None, ge=1),
):
    token = get_access_token(request)
    hub = get_project_forms_hub()
    projects: list = []
    groups: list = []
    selected_project = None
    error = None
    try:
        projects = await fetch_projects(token)
    except Exception as e:
        error = _err_msg(e)

    if project_id:
        selected_project = next(
            (p for p in projects if int(p.get("id") or 0) == int(project_id)),
            None,
        )
        if selected_project:
            try:
                data = await list_instances(token, project_id=project_id)
                groups = group_instances_by_phase(data.get("items") or [])
            except Exception as e:
                error = _err_msg(e)
        else:
            error = error or "Không tìm thấy dự án."

    total_instances = sum(g["count"] for g in groups)
    return templates.TemplateResponse(
        "pages/forms/project_forms.html",
        {
            "request": request,
            "title": hub["name"],
            "hub": hub,
            "projects": projects,
            "project_id": project_id,
            "selected_project": selected_project,
            "groups": groups,
            "total_instances": total_instances,
            "error": error,
        },
    )


@router.get("/phieu-tra-gia")
async def legacy_bid_sheet_list():
    return RedirectResponse(url="/bieu-mau/trong-phien/phieu-tra-gia", status_code=301)


@router.get("/phieu-tra-gia/dau-thuong")
async def legacy_bid_sheet_studio():
    return RedirectResponse(
        url="/bieu-mau/trong-phien/phieu-tra-gia/dau-thuong", status_code=301
    )
