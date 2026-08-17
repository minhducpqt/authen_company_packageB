# routers/forms_hub.py — Hub biểu mẫu theo giai đoạn phiên (add-on, tách production print)
from __future__ import annotations

from typing import Optional
from urllib.parse import quote

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
    project_docgen_actions,
    project_workflow_steps,
    template_source_for_item,
)
from utils.templates import templates

router = APIRouter(tags=["forms-hub"])

_PF_PROJECT_COOKIE = "pf_project_id"
_PF_PROJECT_COOKIE_MAX_AGE = 365 * 24 * 3600


def _parse_project_id(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        pid = int(text)
    except ValueError:
        return None
    return pid if pid >= 1 else None


def _project_exists(projects: list, project_id: int) -> bool:
    return any(int(p.get("id") or 0) == int(project_id) for p in projects)


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
async def forms_by_project(request: Request):
    token = get_access_token(request)
    hub = get_project_forms_hub()
    projects: list = []
    groups: list = []
    instances: list = []
    docgen_actions: dict = {}
    workflow_steps: list = []
    selected_project = None
    error = request.query_params.get("error")
    clear_saved_project = request.query_params.get("clear_project") == "1"
    project_id = None if clear_saved_project else _parse_project_id(
        request.query_params.get("project_id")
    )

    try:
        projects = await fetch_projects(token)
    except Exception as e:
        error = _err_msg(e)

    if not project_id and not clear_saved_project:
        saved_pid = _parse_project_id(request.cookies.get(_PF_PROJECT_COOKIE))
        if saved_pid and _project_exists(projects, saved_pid):
            url = f"/bieu-mau/theo-du-an?project_id={saved_pid}"
            if error:
                url += f"&error={quote(error)}"
            return RedirectResponse(url, status_code=302)

    if project_id:
        selected_project = next(
            (p for p in projects if int(p.get("id") or 0) == int(project_id)),
            None,
        )
        if selected_project:
            try:
                data = await list_instances(token, project_id=project_id)
                instances = data.get("items") or []
                groups = group_instances_by_phase(instances)
                docgen_actions = project_docgen_actions(instances, project_id=project_id)
                workflow_steps = project_workflow_steps(instances, project_id=project_id)
            except Exception as e:
                error = _err_msg(e)
        else:
            error = error or "Không tìm thấy dự án."

    total_instances = len(instances) if instances else sum(g["count"] for g in groups)
    response = templates.TemplateResponse(
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
            "docgen_actions": docgen_actions,
            "workflow_steps": workflow_steps,
            "error": error,
        },
    )
    if project_id and selected_project:
        response.set_cookie(
            _PF_PROJECT_COOKIE,
            str(project_id),
            max_age=_PF_PROJECT_COOKIE_MAX_AGE,
            path="/bieu-mau",
            samesite="lax",
            httponly=False,
        )
    elif clear_saved_project or (project_id and not selected_project):
        response.delete_cookie(_PF_PROJECT_COOKIE, path="/bieu-mau")
    return response


@router.get("/theo-du-an/sinh-quy-che")
async def spawn_regulations_from_project(
    request: Request,
    project_id: int = Query(..., ge=1),
):
    """Sinh quy chế từ hợp đồng đã chốt của dự án (entry từ «Theo dự án»)."""
    token = get_access_token(request)
    back = f"/bieu-mau/theo-du-an?project_id={project_id}"
    try:
        data = await list_instances(
            token,
            phase_slug="truoc-phien",
            category_slug="hop-dong",
            project_id=project_id,
        )
        contracts = data.get("items") or []
        if not contracts:
            return RedirectResponse(
                f"{back}&error={quote('Dự án chưa có hợp đồng.')}",
                status_code=303,
            )
        contract = contracts[0]
        if contract.get("status") != "FINAL":
            return RedirectResponse(
                f"{back}&error={quote('Cần chốt hợp đồng trước khi sinh quy chế.')}",
                status_code=303,
            )
        return RedirectResponse(
            f"/bieu-mau/truoc-phien/quy-che/tao-tu-hop-dong/{contract['id']}",
            status_code=303,
        )
    except Exception as e:
        return RedirectResponse(f"{back}&error={quote(_err_msg(e))}", status_code=303)


@router.get("/phieu-tra-gia")
async def legacy_bid_sheet_list():
    return RedirectResponse(url="/bieu-mau/trong-phien/phieu-tra-gia", status_code=301)


@router.get("/phieu-tra-gia/dau-thuong")
async def legacy_bid_sheet_studio():
    return RedirectResponse(
        url="/bieu-mau/trong-phien/phieu-tra-gia/dau-thuong", status_code=301
    )
