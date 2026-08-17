# routers/docgen_v1.py — UI module Sinh văn bản (proxy Service A)
from __future__ import annotations

import json
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from services.docgen_v1_client import (
    create_instance,
    create_locality_profile,
    delete_locality_profile,
    fetch_communes,
    fetch_provinces,
    fetch_projects,
    finalize_instance,
    get_instance,
    get_locality_profile,
    get_render_context,
    list_instances,
    list_locality_profiles,
    reopen_instance,
    update_instance,
    update_locality_profile,
)
from utils.auth import fetch_me, get_access_token
from utils.document_templates.registry import DocKind, company_code_from_me, resolve_template
from utils.docgen_contract_render import (
    attachment_content_disposition,
    ctx_for_editor,
    download_filename,
    html_to_pdf_bytes,
    merge_fields_for_render,
    merge_ctx_values_for_render,
    render_contract_html,
)
from utils.docgen_regulations_render import (
    merge_ctx_values_for_render as merge_reg_ctx_values,
    merge_fields_for_render as merge_reg_fields,
    render_regulations_html,
)
from utils.forms_catalog.catalog import get_form_item, get_phase, list_config_items
from utils.templates import templates

router = APIRouter(tags=["docgen-v1"])


async def _token(request: Request) -> Optional[str]:
    return get_access_token(request)


def _err_msg(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return str(exc)
    return "Không thể kết nối Service A"


# ---------------------------------------------------------------------------
# Cấu hình — Địa phương
# ---------------------------------------------------------------------------

@router.get("/cau-hinh/dia-phuong", response_class=HTMLResponse)
async def locality_config_list(request: Request):
    token = await _token(request)
    profiles = []
    error = None
    try:
        profiles = await list_locality_profiles(token)
    except Exception as e:
        error = _err_msg(e)
    return templates.TemplateResponse(
        "pages/forms/docgen/locality_list.html",
        {
            "request": request,
            "title": "Cấu hình địa phương",
            "profiles": profiles,
            "error": error,
        },
    )


@router.get("/cau-hinh/dia-phuong/tao", response_class=HTMLResponse)
async def locality_config_new(request: Request):
    provinces = await fetch_provinces()
    return templates.TemplateResponse(
        "pages/forms/docgen/locality_edit.html",
        {
            "request": request,
            "title": "Thêm cấu hình địa phương",
            "profile": None,
            "provinces": provinces,
            "communes": [],
            "error": None,
        },
    )


@router.get("/cau-hinh/dia-phuong/{profile_id}", response_class=HTMLResponse)
async def locality_config_edit(request: Request, profile_id: int):
    token = await _token(request)
    provinces = await fetch_provinces()
    try:
        profile = await get_locality_profile(token, profile_id)
    except Exception as e:
        return templates.TemplateResponse(
            "pages/forms/docgen/locality_list.html",
            {"request": request, "title": "Cấu hình địa phương", "profiles": [], "error": _err_msg(e)},
        )
    communes = []
    # ward_code alone — user re-picks province if needed
    return templates.TemplateResponse(
        "pages/forms/docgen/locality_edit.html",
        {
            "request": request,
            "title": "Sửa cấu hình địa phương",
            "profile": profile,
            "provinces": provinces,
            "communes": communes,
            "error": None,
        },
    )


@router.post("/cau-hinh/dia-phuong/tao", response_class=HTMLResponse)
async def locality_config_create_post(
    request: Request,
    ward_code: int = Form(...),
    label: str = Form(""),
    party_a_name: str = Form(""),
    party_a_address: str = Form(""),
    party_a_tax_code: str = Form(""),
    party_a_treasury_account: str = Form(""),
    party_a_treasury_office: str = Form(""),
    rep_name: str = Form(""),
    rep_department: str = Form(""),
    rep_title: str = Form(""),
    rep_authorization: str = Form(""),
    signing_place: str = Form(""),
    dossier_reception_place: str = Form(""),
    auction_venue: str = Form(""),
):
    token = await _token(request)
    body = {
        "ward_code": ward_code,
        "label": label or None,
        "party_a": {
            "name": party_a_name,
            "address": party_a_address,
            "tax_code": party_a_tax_code,
            "treasury_account": party_a_treasury_account,
            "treasury_office": party_a_treasury_office,
        },
        "representative": {
            "name": rep_name,
            "department": rep_department,
            "title": rep_title,
            "authorization": rep_authorization,
        },
        "defaults": {
            "signing_place": signing_place,
            "dossier_reception_place": dossier_reception_place,
            "auction_venue": auction_venue,
        },
    }
    try:
        prof = await create_locality_profile(token, body)
        return RedirectResponse(f"/bieu-mau/cau-hinh/dia-phuong/{prof['id']}", status_code=303)
    except Exception as e:
        provinces = await fetch_provinces()
        return templates.TemplateResponse(
            "pages/forms/docgen/locality_edit.html",
            {
                "request": request,
                "title": "Thêm cấu hình địa phương",
                "profile": None,
                "provinces": provinces,
                "communes": [],
                "error": _err_msg(e),
                "form": body,
            },
        )


@router.post("/cau-hinh/dia-phuong/{profile_id}", response_class=HTMLResponse)
async def locality_config_update_post(
    request: Request,
    profile_id: int,
    label: str = Form(""),
    party_a_name: str = Form(""),
    party_a_address: str = Form(""),
    party_a_tax_code: str = Form(""),
    party_a_treasury_account: str = Form(""),
    party_a_treasury_office: str = Form(""),
    rep_name: str = Form(""),
    rep_department: str = Form(""),
    rep_title: str = Form(""),
    rep_authorization: str = Form(""),
    signing_place: str = Form(""),
    dossier_reception_place: str = Form(""),
    auction_venue: str = Form(""),
):
    token = await _token(request)
    body = {
        "label": label or None,
        "party_a": {
            "name": party_a_name,
            "address": party_a_address,
            "tax_code": party_a_tax_code,
            "treasury_account": party_a_treasury_account,
            "treasury_office": party_a_treasury_office,
        },
        "representative": {
            "name": rep_name,
            "department": rep_department,
            "title": rep_title,
            "authorization": rep_authorization,
        },
        "defaults": {
            "signing_place": signing_place,
            "dossier_reception_place": dossier_reception_place,
            "auction_venue": auction_venue,
        },
    }
    try:
        await update_locality_profile(token, profile_id, body)
        return RedirectResponse(f"/bieu-mau/cau-hinh/dia-phuong/{profile_id}", status_code=303)
    except Exception as e:
        provinces = await fetch_provinces()
        profile = await get_locality_profile(token, profile_id)
        return templates.TemplateResponse(
            "pages/forms/docgen/locality_edit.html",
            {
                "request": request,
                "title": "Sửa cấu hình địa phương",
                "profile": profile,
                "provinces": provinces,
                "communes": [],
                "error": _err_msg(e),
            },
        )


@router.post("/cau-hinh/dia-phuong/{profile_id}/xoa", response_class=HTMLResponse)
async def locality_config_delete(request: Request, profile_id: int):
    token = await _token(request)
    try:
        await delete_locality_profile(token, profile_id)
    except Exception:
        pass
    return RedirectResponse("/bieu-mau/cau-hinh/dia-phuong", status_code=303)


@router.get("/api/communes", response_class=HTMLResponse)
async def api_communes(province_code: int, q: Optional[str] = None):
    items = await fetch_communes(province_code, q)
    return HTMLResponse(json.dumps({"items": items}, ensure_ascii=False), media_type="application/json")


# ---------------------------------------------------------------------------
# Hợp đồng — danh sách & tạo
# ---------------------------------------------------------------------------

@router.get("/truoc-phien/hop-dong", response_class=HTMLResponse)
async def contract_list(request: Request):
    token = await _token(request)
    phase = get_phase("pre_session")
    item = get_form_item("pre_session", "hop-dong")
    instances = []
    error = None
    try:
        data = await list_instances(token, phase_slug="truoc-phien", category_slug="hop-dong")
        instances = data.get("items") or []
    except Exception as e:
        error = _err_msg(e)
    return templates.TemplateResponse(
        "pages/forms/docgen/contract_list.html",
        {
            "request": request,
            "title": "Hợp đồng — Trước phiên",
            "phase": phase,
            "item": item,
            "instances": instances,
            "error": error,
        },
    )


@router.get("/truoc-phien/hop-dong/tao", response_class=HTMLResponse)
async def contract_create_page(
    request: Request,
    project_id: Optional[int] = Query(None, ge=1),
):
    token = await _token(request)
    phase = get_phase("pre_session")
    item = get_form_item("pre_session", "hop-dong")
    projects = []
    projects_with_contract: Dict[int, int] = {}
    provinces = await fetch_provinces()
    error = None
    try:
        projects = await fetch_projects(token)
        data = await list_instances(token, phase_slug="truoc-phien", category_slug="hop-dong")
        for inst in data.get("items") or []:
            pid = inst.get("project_id")
            if pid:
                projects_with_contract[int(pid)] = int(inst["id"])
    except Exception as e:
        error = _err_msg(e)
    return templates.TemplateResponse(
        "pages/forms/docgen/contract_create.html",
        {
            "request": request,
            "title": "Tạo hợp đồng",
            "phase": phase,
            "item": item,
            "projects": projects,
            "projects_with_contract": projects_with_contract,
            "provinces": provinces,
            "preselected_project_id": project_id,
            "error": error,
        },
    )


@router.post("/truoc-phien/hop-dong/tao", response_class=HTMLResponse)
async def contract_create_post(
    request: Request,
    project_id: int = Form(...),
    ward_code: Optional[int] = Form(None),
):
    token = await _token(request)
    body = {
        "template_key": "service_contract_v1",
        "phase_slug": "truoc-phien",
        "category_slug": "hop-dong",
        "project_id": project_id,
        "ward_code": ward_code or None,
    }
    try:
        inst = await create_instance(token, body)
        return RedirectResponse(f"/bieu-mau/truoc-phien/hop-dong/{inst['id']}", status_code=303)
    except Exception as e:
        phase = get_phase("pre_session")
        item = get_form_item("pre_session", "hop-dong")
        projects = await fetch_projects(token)
        provinces = await fetch_provinces()
        projects_with_contract: Dict[int, int] = {}
        try:
            data = await list_instances(token, phase_slug="truoc-phien", category_slug="hop-dong")
            for inst in data.get("items") or []:
                pid = inst.get("project_id")
                if pid:
                    projects_with_contract[int(pid)] = int(inst["id"])
        except Exception:
            pass
        return templates.TemplateResponse(
            "pages/forms/docgen/contract_create.html",
            {
                "request": request,
                "title": "Tạo hợp đồng",
                "phase": phase,
                "item": item,
                "projects": projects,
                "projects_with_contract": projects_with_contract,
                "provinces": provinces,
                "error": _err_msg(e),
            },
        )


async def _render_contract(
    request: Request,
    token: Optional[str],
    instance_id: int,
    cc: str,
    *,
    fields_override: Optional[Dict[str, Any]] = None,
    overrides_override: Optional[Dict[str, Any]] = None,
    persist: bool = False,
    for_download: bool = False,
) -> tuple[str, Dict[str, Any], Dict[str, Any], str]:
    tpl = resolve_template(cc, DocKind.SERVICE_CONTRACT)
    if persist and (fields_override is not None or overrides_override is not None):
        body: Dict[str, Any] = {}
        if fields_override is not None:
            body["fields"] = fields_override
        if overrides_override is not None:
            body["overrides"] = overrides_override
        await update_instance(token, instance_id, body)
    inst = await get_instance(token, instance_id)
    ctx = await get_render_context(token, instance_id)
    fields = merge_fields_for_render(
        inst,
        ctx,
        fields_override if fields_override is not None else inst.get("fields"),
    )
    ov = overrides_override if overrides_override is not None else (inst.get("overrides") or {})
    ctx = merge_ctx_values_for_render(ctx, fields, ov)
    html = await render_contract_html(
        request,
        template_path=tpl,
        ctx=ctx,
        fields=fields,
        for_download=for_download,
    )
    return html, inst, ctx, tpl


@router.get("/truoc-phien/hop-dong/{instance_id}", response_class=HTMLResponse)
async def contract_editor(request: Request, instance_id: int):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    phase = get_phase("pre_session")
    item = get_form_item("pre_session", "hop-dong")
    tpl = resolve_template(cc, DocKind.SERVICE_CONTRACT)
    try:
        inst = await get_instance(token, instance_id)
        ctx = await get_render_context(token, instance_id)
    except Exception as e:
        return RedirectResponse(f"/bieu-mau/truoc-phien/hop-dong?error={_err_msg(e)}", status_code=303)
    regulations_id = None
    try:
        data = await list_instances(
            token,
            phase_slug="truoc-phien",
            category_slug="quy-che",
            project_id=inst.get("project_id"),
        )
        items = data.get("items") or []
        if items:
            regulations_id = items[0].get("id")
    except Exception:
        pass
    fields_json = json.dumps(inst.get("fields") or {}, ensure_ascii=False)
    overrides_json = json.dumps(inst.get("overrides") or {}, ensure_ascii=False)
    provinces = await fetch_provinces()
    return templates.TemplateResponse(
        "pages/forms/docgen/contract_editor.html",
        {
            "request": request,
            "title": inst.get("title") or "Hợp đồng",
            "phase": phase,
            "item": item,
            "instance": inst,
            "fields_json": fields_json,
            "overrides_json": overrides_json,
            "ctx_json": ctx_for_editor(ctx),
            "provinces": provinces,
            "preview_url": f"/bieu-mau/truoc-phien/hop-dong/{instance_id}/preview",
            "download_html_url": f"/bieu-mau/truoc-phien/hop-dong/{instance_id}/tai-html",
            "download_pdf_url": f"/bieu-mau/truoc-phien/hop-dong/{instance_id}/tai-pdf",
            "template_path": tpl,
            "company_code": cc,
            "is_final": inst.get("status") == "FINAL",
            "regulations_id": regulations_id,
            "regulations_create_url": f"/bieu-mau/truoc-phien/quy-che/tao-tu-hop-dong/{instance_id}",
        },
    )


@router.post("/truoc-phien/hop-dong/{instance_id}/doi-xa", response_class=HTMLResponse)
async def contract_change_ward(
    request: Request,
    instance_id: int,
    ward_code: int = Form(...),
):
    token = await _token(request)
    try:
        inst = await get_instance(token, instance_id)
        if inst.get("status") == "FINAL":
            return RedirectResponse(f"/bieu-mau/truoc-phien/hop-dong/{instance_id}", status_code=303)
        await update_instance(token, instance_id, {"ward_code": ward_code})
    except Exception:
        pass
    return RedirectResponse(f"/bieu-mau/truoc-phien/hop-dong/{instance_id}", status_code=303)


@router.post("/truoc-phien/hop-dong/{instance_id}/save", response_class=HTMLResponse)
async def contract_save(
    request: Request,
    instance_id: int,
    title: str = Form(""),
    document_no: str = Form(""),
    fields_json: str = Form("{}"),
    overrides_json: str = Form("{}"),
):
    token = await _token(request)
    try:
        fields = json.loads(fields_json or "{}")
    except json.JSONDecodeError:
        fields = {}
    try:
        overrides = json.loads(overrides_json or "{}")
    except json.JSONDecodeError:
        overrides = {}
    body = {
        "title": title or None,
        "document_no": document_no or None,
        "fields": fields,
        "overrides": overrides,
    }
    try:
        await update_instance(token, instance_id, body)
    except Exception:
        pass
    return RedirectResponse(f"/bieu-mau/truoc-phien/hop-dong/{instance_id}", status_code=303)


@router.post("/truoc-phien/hop-dong/{instance_id}/finalize", response_class=HTMLResponse)
async def contract_finalize(request: Request, instance_id: int):
    token = await _token(request)
    try:
        await finalize_instance(token, instance_id)
    except Exception:
        pass
    return RedirectResponse(f"/bieu-mau/truoc-phien/hop-dong/{instance_id}", status_code=303)


@router.post("/truoc-phien/hop-dong/{instance_id}/reopen", response_class=HTMLResponse)
async def contract_reopen(request: Request, instance_id: int):
    token = await _token(request)
    try:
        await reopen_instance(token, instance_id)
    except Exception:
        pass
    return RedirectResponse(f"/bieu-mau/truoc-phien/hop-dong/{instance_id}", status_code=303)


@router.post("/truoc-phien/hop-dong/{instance_id}/preview", response_class=HTMLResponse)
async def contract_preview(request: Request, instance_id: int, fields_json: str = Form("{}"), overrides_json: str = Form("{}")):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    try:
        fields = json.loads(fields_json or "{}")
    except json.JSONDecodeError:
        fields = {}
    try:
        overrides = json.loads(overrides_json or "{}")
    except json.JSONDecodeError:
        overrides = {}
    try:
        html, _, _, _ = await _render_contract(
            request,
            token,
            instance_id,
            cc,
            fields_override=fields,
            overrides_override=overrides,
            persist=False,
        )
    except Exception as e:
        return HTMLResponse(f"<pre>Preview error: {_err_msg(e)}</pre>", status_code=500)
    return HTMLResponse(html)


@router.get("/truoc-phien/hop-dong/{instance_id}/tai-html")
async def contract_download_html(request: Request, instance_id: int):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    try:
        html, inst, _, _ = await _render_contract(request, token, instance_id, cc, for_download=True)
    except Exception as e:
        return HTMLResponse(f"Error: {_err_msg(e)}", status_code=500)
    fname = download_filename(inst, "html")
    return Response(
        content=html.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": attachment_content_disposition(fname)},
    )


@router.get("/truoc-phien/hop-dong/{instance_id}/tai-pdf")
async def contract_download_pdf(request: Request, instance_id: int):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    try:
        html, inst, _, _ = await _render_contract(request, token, instance_id, cc, for_download=True)
        pdf_bytes = html_to_pdf_bytes(html)
    except Exception as e:
        return HTMLResponse(f"Không tạo được PDF: {_err_msg(e)}", status_code=500)
    fname = download_filename(inst, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment_content_disposition(fname)},
    )


# Config hub shortcut
@router.get("/cau-hinh", response_class=HTMLResponse)
async def config_hub(request: Request):
    return RedirectResponse("/bieu-mau/cau-hinh/dia-phuong", status_code=302)


# ---------------------------------------------------------------------------
# Quy chế — danh sách & tạo
# ---------------------------------------------------------------------------

@router.get("/truoc-phien/quy-che")
async def regulations_list(request: Request):
    return RedirectResponse("/bieu-mau/theo-du-an", status_code=302)


@router.get("/truoc-phien/quy-che/tao", response_class=HTMLResponse)
async def regulations_create_page(request: Request):
    return RedirectResponse("/bieu-mau/theo-du-an", status_code=302)


@router.post("/truoc-phien/quy-che/tao", response_class=HTMLResponse)
async def regulations_create_post(
    request: Request,
    project_id: int = Form(...),
    ward_code: Optional[int] = Form(None),
):
    return RedirectResponse(
        f"/bieu-mau/theo-du-an?project_id={project_id}&error={quote('Sinh quy chế từ mục «Theo dự án» sau khi đã chốt hợp đồng.')}",
        status_code=303,
    )


@router.get("/truoc-phien/quy-che/tao-tu-hop-dong/{contract_id}", response_class=HTMLResponse)
async def regulations_create_from_contract(request: Request, contract_id: int):
    """Tạo hoặc mở quy chế cho cùng dự án với hợp đồng đã chốt."""
    token = await _token(request)
    try:
        contract = await get_instance(token, contract_id)
    except Exception as e:
        return RedirectResponse(f"/bieu-mau/truoc-phien/hop-dong?error={_err_msg(e)}", status_code=303)
    project_id = contract.get("project_id")
    if contract.get("status") != "FINAL":
        back = f"/bieu-mau/theo-du-an?project_id={project_id}" if project_id else "/bieu-mau/theo-du-an"
        return RedirectResponse(
            f"{back}&error={quote('Cần chốt hợp đồng trước khi sinh quy chế.')}",
            status_code=303,
        )
    ward_code = contract.get("ward_code")
    try:
        data = await list_instances(
            token,
            phase_slug="truoc-phien",
            category_slug="quy-che",
            project_id=project_id,
        )
        items = data.get("items") or []
        if items:
            return RedirectResponse(f"/bieu-mau/truoc-phien/quy-che/{items[0]['id']}", status_code=303)
    except Exception:
        pass
    body = {
        "template_key": "auction_regulations_v1",
        "phase_slug": "truoc-phien",
        "category_slug": "quy-che",
        "project_id": project_id,
        "ward_code": ward_code,
    }
    try:
        inst = await create_instance(token, body)
        return RedirectResponse(f"/bieu-mau/truoc-phien/quy-che/{inst['id']}", status_code=303)
    except Exception as e:
        back = f"/bieu-mau/theo-du-an?project_id={project_id}" if project_id else "/bieu-mau/theo-du-an"
        return RedirectResponse(f"{back}&error={quote(_err_msg(e))}", status_code=303)


async def _render_regulations(
    request: Request,
    token: Optional[str],
    instance_id: int,
    cc: str,
    *,
    fields_override: Optional[Dict[str, Any]] = None,
    overrides_override: Optional[Dict[str, Any]] = None,
    persist: bool = False,
    for_download: bool = False,
) -> tuple[str, Dict[str, Any], Dict[str, Any], str]:
    tpl = resolve_template(cc, DocKind.AUCTION_REGULATIONS)
    if persist and (fields_override is not None or overrides_override is not None):
        body: Dict[str, Any] = {}
        if fields_override is not None:
            body["fields"] = fields_override
        if overrides_override is not None:
            body["overrides"] = overrides_override
        await update_instance(token, instance_id, body)
    inst = await get_instance(token, instance_id)
    ctx = await get_render_context(token, instance_id)
    fields = merge_reg_fields(
        inst,
        ctx,
        fields_override if fields_override is not None else inst.get("fields"),
    )
    ov = overrides_override if overrides_override is not None else (inst.get("overrides") or {})
    ctx = merge_reg_ctx_values(ctx, fields, ov)
    html = await render_regulations_html(
        request,
        template_path=tpl,
        ctx=ctx,
        fields=fields,
        for_download=for_download,
    )
    return html, inst, ctx, tpl


@router.get("/truoc-phien/quy-che/{instance_id}", response_class=HTMLResponse)
async def regulations_editor(request: Request, instance_id: int):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    phase = get_phase("pre_session")
    item = get_form_item("pre_session", "quy-che")
    tpl = resolve_template(cc, DocKind.AUCTION_REGULATIONS)
    try:
        inst = await get_instance(token, instance_id)
        ctx = await get_render_context(token, instance_id)
    except Exception as e:
        return RedirectResponse(
            f"/bieu-mau/theo-du-an?error={quote(_err_msg(e))}",
            status_code=303,
        )
    contract_id = None
    try:
        data = await list_instances(
            token,
            phase_slug="truoc-phien",
            category_slug="hop-dong",
            project_id=inst.get("project_id"),
        )
        items = data.get("items") or []
        if items:
            contract_id = items[0].get("id")
    except Exception:
        pass
    fields_json = json.dumps(inst.get("fields") or {}, ensure_ascii=False)
    overrides_json = json.dumps(inst.get("overrides") or {}, ensure_ascii=False)
    provinces = await fetch_provinces()
    return templates.TemplateResponse(
        "pages/forms/docgen/regulations_editor.html",
        {
            "request": request,
            "title": inst.get("title") or "Quy chế",
            "phase": phase,
            "item": item,
            "instance": inst,
            "fields_json": fields_json,
            "overrides_json": overrides_json,
            "ctx_json": ctx_for_editor(ctx),
            "provinces": provinces,
            "preview_url": f"/bieu-mau/truoc-phien/quy-che/{instance_id}/preview",
            "download_html_url": f"/bieu-mau/truoc-phien/quy-che/{instance_id}/tai-html",
            "download_pdf_url": f"/bieu-mau/truoc-phien/quy-che/{instance_id}/tai-pdf",
            "template_path": tpl,
            "company_code": cc,
            "is_final": inst.get("status") == "FINAL",
            "contract_id": contract_id,
            "project_forms_url": f"/bieu-mau/theo-du-an?project_id={inst.get('project_id')}" if inst.get("project_id") else "/bieu-mau/theo-du-an",
        },
    )


@router.post("/truoc-phien/quy-che/{instance_id}/doi-xa", response_class=HTMLResponse)
async def regulations_change_ward(
    request: Request,
    instance_id: int,
    ward_code: int = Form(...),
):
    token = await _token(request)
    try:
        inst = await get_instance(token, instance_id)
        if inst.get("status") == "FINAL":
            return RedirectResponse(f"/bieu-mau/truoc-phien/quy-che/{instance_id}", status_code=303)
        await update_instance(token, instance_id, {"ward_code": ward_code})
    except Exception:
        pass
    return RedirectResponse(f"/bieu-mau/truoc-phien/quy-che/{instance_id}", status_code=303)


@router.post("/truoc-phien/quy-che/{instance_id}/save", response_class=HTMLResponse)
async def regulations_save(
    request: Request,
    instance_id: int,
    title: str = Form(""),
    document_no: str = Form(""),
    fields_json: str = Form("{}"),
    overrides_json: str = Form("{}"),
):
    token = await _token(request)
    try:
        fields = json.loads(fields_json or "{}")
    except json.JSONDecodeError:
        fields = {}
    try:
        overrides = json.loads(overrides_json or "{}")
    except json.JSONDecodeError:
        overrides = {}
    body = {
        "title": title or None,
        "document_no": document_no or None,
        "fields": fields,
        "overrides": overrides,
    }
    try:
        await update_instance(token, instance_id, body)
    except Exception:
        pass
    return RedirectResponse(f"/bieu-mau/truoc-phien/quy-che/{instance_id}", status_code=303)


@router.post("/truoc-phien/quy-che/{instance_id}/finalize", response_class=HTMLResponse)
async def regulations_finalize(request: Request, instance_id: int):
    token = await _token(request)
    try:
        await finalize_instance(token, instance_id)
    except Exception:
        pass
    return RedirectResponse(f"/bieu-mau/truoc-phien/quy-che/{instance_id}", status_code=303)


@router.post("/truoc-phien/quy-che/{instance_id}/reopen", response_class=HTMLResponse)
async def regulations_reopen(request: Request, instance_id: int):
    token = await _token(request)
    try:
        await reopen_instance(token, instance_id)
    except Exception:
        pass
    return RedirectResponse(f"/bieu-mau/truoc-phien/quy-che/{instance_id}", status_code=303)


@router.post("/truoc-phien/quy-che/{instance_id}/preview", response_class=HTMLResponse)
async def regulations_preview(
    request: Request,
    instance_id: int,
    fields_json: str = Form("{}"),
    overrides_json: str = Form("{}"),
):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    try:
        fields = json.loads(fields_json or "{}")
    except json.JSONDecodeError:
        fields = {}
    try:
        overrides = json.loads(overrides_json or "{}")
    except json.JSONDecodeError:
        overrides = {}
    try:
        html, _, _, _ = await _render_regulations(
            request,
            token,
            instance_id,
            cc,
            fields_override=fields,
            overrides_override=overrides,
            persist=False,
        )
    except Exception as e:
        return HTMLResponse(f"<pre>Preview error: {_err_msg(e)}</pre>", status_code=500)
    return HTMLResponse(html)


@router.get("/truoc-phien/quy-che/{instance_id}/tai-html")
async def regulations_download_html(request: Request, instance_id: int):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    try:
        html, inst, _, _ = await _render_regulations(request, token, instance_id, cc, for_download=True)
    except Exception as e:
        return HTMLResponse(f"Error: {_err_msg(e)}", status_code=500)
    from utils.docgen_regulations_render import download_filename as reg_download_filename

    fname = reg_download_filename(inst, "html")
    return Response(
        content=html.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": attachment_content_disposition(fname)},
    )


@router.get("/truoc-phien/quy-che/{instance_id}/tai-pdf")
async def regulations_download_pdf(request: Request, instance_id: int):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    try:
        html, inst, _, _ = await _render_regulations(request, token, instance_id, cc, for_download=True)
        pdf_bytes = html_to_pdf_bytes(html)
    except Exception as e:
        return HTMLResponse(f"Không tạo được PDF: {_err_msg(e)}", status_code=500)
    from utils.docgen_regulations_render import download_filename as reg_download_filename

    fname = reg_download_filename(inst, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment_content_disposition(fname)},
    )
