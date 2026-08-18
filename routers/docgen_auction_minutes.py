# routers/docgen_auction_minutes.py — Biên bản đấu giá TP-ĐGTS-18 (docgen instance)
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from routers.auction_documents_print import build_session_progress_data
from services.docgen_v1_client import (
    create_instance,
    finalize_instance,
    get_instance,
    get_render_context,
    list_auctioneers,
    list_instances,
    reopen_instance,
    update_instance,
)
from utils.auth import fetch_me, get_access_token
from utils.docgen_auction_minutes_render import (
    DEFAULT_BIDDERS_NOTE,
    attachment_content_disposition,
    download_filename,
    html_to_pdf_bytes,
    render_auction_minutes_html,
)
from utils.docgen_contract_render import ctx_for_editor
from utils.document_templates.registry import DocKind, company_code_from_me, resolve_template
from utils.forms_catalog.catalog import get_form_item, get_phase
from utils.templates import templates

router = APIRouter(tags=["docgen-auction-minutes"])

_SERVICE_A_BASE = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


async def _token(request: Request) -> Optional[str]:
    return get_access_token(request)


def _err_msg(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return str(exc)
    return "Không thể kết nối Service A"


def _company_display_name(ctx: Optional[Dict[str, Any]], me: Optional[Dict[str, Any]] = None) -> str:
    if isinstance(ctx, dict):
        co = ctx.get("company") if isinstance(ctx.get("company"), dict) else {}
        name = str(co.get("name") or "").strip()
        if name:
            return name
    if me:
        for key in ("company_name", "org_name", "company"):
            val = str(me.get(key) or "").strip()
            if val:
                return val
    return ""


def _pick_master_auctioneer(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for row in rows or []:
        if row.get("is_master"):
            return row
    return rows[0] if rows else None


def _apply_minutes_defaults(
    fields: Dict[str, Any],
    *,
    ctx: Optional[Dict[str, Any]],
    me: Optional[Dict[str, Any]],
    master_auctioneer: Optional[Dict[str, Any]],
) -> tuple[Dict[str, Any], bool]:
    out = dict(fields or {})
    minutes = dict(out.get("minutes") or {})
    changed = False

    cname = _company_display_name(ctx, me)
    if not (minutes.get("organizer") or "").strip() and cname:
        minutes["organizer"] = cname
        changed = True

    if master_auctioneer:
        mid = master_auctioneer.get("id")
        if not minutes.get("auctioneer_id") and mid:
            minutes["auctioneer_id"] = int(mid)
            changed = True
        if not (minutes.get("auctioneer_name") or "").strip():
            minutes["auctioneer_name"] = str(master_auctioneer.get("full_name") or "").strip()
            changed = True
        if not (minutes.get("auctioneer_certificate_no") or "").strip():
            minutes["auctioneer_certificate_no"] = str(
                master_auctioneer.get("certificate_no") or ""
            ).strip()
            changed = True

    if not (minutes.get("bidders_note") or "").strip():
        minutes["bidders_note"] = DEFAULT_BIDDERS_NOTE
        changed = True

    if not isinstance(minutes.get("guests"), list):
        minutes["guests"] = []
        changed = True

    if "progression" not in minutes or not isinstance(minutes.get("progression"), dict):
        minutes["progression"] = {
            "failed_lots": [],
            "won_lots": [],
            "eligible_lots": [],
            "round_sections": [],
            "summary": {},
            "price_labels": {},
            "synced_at": "",
        }
        changed = True

    out["minutes"] = minutes
    return out, changed


def _merge_progression_into_minutes(
    minutes: Dict[str, Any],
    prog: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(minutes or {})
    snap = {
        "failed_lots": prog.get("failed_lots") or [],
        "won_lots": prog.get("won_lots") or [],
        "eligible_lots": prog.get("eligible_lots") or [],
        "round_sections": prog.get("round_sections") or [],
        "summary": prog.get("summary") or {},
        "price_labels": prog.get("price_labels") or {},
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "error": prog.get("error"),
    }
    out["progression"] = snap
    out["failed_lots"] = snap["failed_lots"]
    out["won_lots"] = snap["won_lots"]
    return out


async def _enrich_minutes_from_session(
    token: Optional[str],
    fields: Dict[str, Any],
) -> Dict[str, Any]:
    """Bổ sung giá khởi điểm lô đủ điều kiện từ phiên khi chưa đồng bộ diễn biến."""
    if not token:
        return fields
    out = dict(fields or {})
    minutes = dict(out.get("minutes") or {})
    session_id = minutes.get("session_id")
    if not session_id:
        return fields
    prog = dict(minutes.get("progression") or {})
    elots = prog.get("eligible_lots") or []
    has_descriptions = bool(elots) and all(
        isinstance(r, dict) and "lot_area_display" in r for r in elots
    )
    if has_descriptions:
        return fields
    try:
        data = await build_session_progress_data(token, int(session_id))
    except Exception:
        return fields
    prog["eligible_lots"] = data.get("eligible_lots") or []
    if not prog.get("price_labels"):
        prog["price_labels"] = data.get("price_labels") or {}
    minutes["progression"] = prog
    out["minutes"] = minutes
    return out


async def _fetch_project_sessions(token: Optional[str], project_id: int) -> List[Dict[str, Any]]:
    if not token or not project_id:
        return []
    url = f"{_SERVICE_A_BASE}/api/v1/auction-sessions/sessions"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                url,
                headers=headers,
                params={"project_id": int(project_id), "page": 1, "size": 100},
            )
        if r.status_code != 200:
            return []
        js = r.json()
        data = js.get("data") if isinstance(js, dict) else None
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        return []
    return []


def _session_sort_key(session: Dict[str, Any]) -> tuple:
    ad = str(session.get("auction_date") or session.get("created_at") or "")
    sid = int(session.get("id") or 0)
    return (ad, sid)


def _pick_latest_session_id(sessions: List[Dict[str, Any]]) -> Optional[int]:
    if not sessions:
        return None
    ordered = sorted(sessions, key=_session_sort_key, reverse=True)
    sid = ordered[0].get("id")
    return int(sid) if sid else None


async def _ensure_session_on_fields(
    token: Optional[str],
    *,
    project_id: int,
    fields: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(fields or {})
    minutes = dict(out.get("minutes") or {})
    if minutes.get("session_id"):
        out["minutes"] = minutes
        return out
    sessions = await _fetch_project_sessions(token, project_id)
    latest = _pick_latest_session_id(sessions)
    if latest:
        minutes["session_id"] = latest
    out["minutes"] = minutes
    return out


async def _render_auction_minutes(
    request: Request,
    token: Optional[str],
    instance_id: int,
    company_code: str,
    *,
    fields_override: Optional[Dict[str, Any]] = None,
    for_download: bool = False,
    for_preview: bool = False,
):
    inst = await get_instance(token, instance_id)
    ctx = await get_render_context(token, instance_id)
    fields = dict(fields_override if fields_override is not None else (inst.get("fields") or {}))
    fields = await _enrich_minutes_from_session(token, fields)
    tpl = resolve_template(company_code or None, DocKind.AUCTION_MINUTES)
    html = render_auction_minutes_html(
        request,
        template_path=tpl,
        fields=fields,
        ctx=ctx,
        instance=inst,
        for_download=for_download,
        for_preview=for_preview,
    )
    return html, inst, ctx, tpl


@router.get("/sau-phien/bien-ban-dau-gia", response_class=HTMLResponse)
async def auction_minutes_hub_redirect(
    request: Request,
    project_id: Optional[int] = Query(None, ge=1),
):
    if project_id:
        return RedirectResponse(
            f"/bieu-mau/theo-du-an?project_id={project_id}#bien-ban-dau-gia",
            status_code=302,
        )
    return RedirectResponse("/bieu-mau/sau-phien", status_code=302)


@router.get("/sau-phien/bien-ban-dau-gia/tao", response_class=HTMLResponse)
async def auction_minutes_create(
    request: Request,
    project_id: int = Query(..., ge=1),
):
    token = await _token(request)
    try:
        data = await list_instances(
            token,
            phase_slug="sau-phien",
            category_slug="bien-ban-dau-gia",
            project_id=project_id,
        )
        items = data.get("items") or []
        if items:
            return RedirectResponse(
                f"/bieu-mau/sau-phien/bien-ban-dau-gia/{items[0]['id']}",
                status_code=303,
            )
    except Exception:
        pass

    body = {
        "template_key": "auction_minutes_v1",
        "phase_slug": "sau-phien",
        "category_slug": "bien-ban-dau-gia",
        "project_id": project_id,
    }
    try:
        inst = await create_instance(token, body)
        me = await fetch_me(token)
        ctx = await get_render_context(token, int(inst["id"]))
        master_row = None
        try:
            auctioneers = await list_auctioneers(token)
            master_row = _pick_master_auctioneer(auctioneers)
        except Exception:
            pass
        fields = dict(inst.get("fields") or {})
        fields, _ = _apply_minutes_defaults(
            fields, ctx=ctx, me=me, master_auctioneer=master_row
        )
        fields = await _ensure_session_on_fields(
            token, project_id=project_id, fields=fields
        )
        if fields != (inst.get("fields") or {}):
            inst = await update_instance(token, int(inst["id"]), {"fields": fields})
        return RedirectResponse(
            f"/bieu-mau/sau-phien/bien-ban-dau-gia/{inst['id']}",
            status_code=303,
        )
    except Exception as e:
        return RedirectResponse(
            f"/bieu-mau/theo-du-an?project_id={project_id}&error={_err_msg(e)}#bien-ban-dau-gia",
            status_code=303,
        )


@router.get("/sau-phien/bien-ban-dau-gia/{instance_id}", response_class=HTMLResponse)
async def auction_minutes_editor(request: Request, instance_id: int):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    phase = get_phase("post_session")
    item = get_form_item("post_session", "bien-ban-dau-gia")
    tpl = resolve_template(cc, DocKind.AUCTION_MINUTES)
    try:
        inst = await get_instance(token, instance_id)
        ctx = await get_render_context(token, instance_id)
    except Exception as e:
        return RedirectResponse(
            f"/bieu-mau/theo-du-an?error={_err_msg(e)}",
            status_code=303,
        )

    pid = int(inst.get("project_id") or 0)
    sessions = await _fetch_project_sessions(token, pid) if pid else []
    fields = dict(inst.get("fields") or {})
    master_row = None
    company_auctioneers: List[Dict[str, Any]] = []
    try:
        company_auctioneers = await list_auctioneers(token)
        master_row = _pick_master_auctioneer(company_auctioneers)
    except Exception:
        pass

    fields, changed = _apply_minutes_defaults(
        fields, ctx=ctx, me=me, master_auctioneer=master_row
    )
    minutes = dict(fields.get("minutes") or {})
    if not minutes.get("session_id") and pid:
        fields = await _ensure_session_on_fields(token, project_id=pid, fields=fields)
        changed = True
    if changed:
        try:
            inst = await update_instance(token, instance_id, {"fields": fields})
        except Exception:
            pass

    project_forms_url = (
        f"/bieu-mau/theo-du-an?project_id={pid}#bien-ban-dau-gia"
        if pid
        else "/bieu-mau/theo-du-an"
    )
    fields_json = json.dumps(inst.get("fields") or {}, ensure_ascii=False)

    return templates.TemplateResponse(
        "pages/forms/docgen/auction_minutes_editor.html",
        {
            "request": request,
            "title": inst.get("title") or "Biên bản đấu giá",
            "phase": phase,
            "item": item,
            "instance": inst,
            "fields_json": fields_json,
            "ctx_json": ctx_for_editor(ctx),
            "auction_sessions": sessions,
            "company_auctioneers": company_auctioneers,
            "preview_url": f"/bieu-mau/sau-phien/bien-ban-dau-gia/{instance_id}/preview",
            "sync_progression_url": f"/bieu-mau/sau-phien/bien-ban-dau-gia/{instance_id}/dong-bo-dien-bien",
            "download_html_url": f"/bieu-mau/sau-phien/bien-ban-dau-gia/{instance_id}/tai-html",
            "download_pdf_url": f"/bieu-mau/sau-phien/bien-ban-dau-gia/{instance_id}/tai-pdf",
            "template_path": tpl,
            "company_code": cc,
            "is_final": inst.get("status") == "FINAL",
            "project_forms_url": project_forms_url,
        },
    )


@router.post("/sau-phien/bien-ban-dau-gia/{instance_id}/save", response_class=HTMLResponse)
async def auction_minutes_save(
    request: Request,
    instance_id: int,
    title: str = Form(""),
    document_no: str = Form(""),
    fields_json: str = Form("{}"),
):
    token = await _token(request)
    try:
        fields = json.loads(fields_json or "{}")
    except json.JSONDecodeError:
        fields = {}
    body = {
        "title": title or None,
        "document_no": document_no or None,
        "fields": fields,
    }
    try:
        await update_instance(token, instance_id, body)
    except Exception:
        pass
    return RedirectResponse(
        f"/bieu-mau/sau-phien/bien-ban-dau-gia/{instance_id}",
        status_code=303,
    )


@router.post("/sau-phien/bien-ban-dau-gia/{instance_id}/finalize", response_class=HTMLResponse)
async def auction_minutes_finalize(request: Request, instance_id: int):
    token = await _token(request)
    try:
        await finalize_instance(token, instance_id)
    except Exception:
        pass
    return RedirectResponse(
        f"/bieu-mau/sau-phien/bien-ban-dau-gia/{instance_id}",
        status_code=303,
    )


@router.post("/sau-phien/bien-ban-dau-gia/{instance_id}/reopen", response_class=HTMLResponse)
async def auction_minutes_reopen(request: Request, instance_id: int):
    token = await _token(request)
    try:
        await reopen_instance(token, instance_id)
    except Exception:
        pass
    return RedirectResponse(
        f"/bieu-mau/sau-phien/bien-ban-dau-gia/{instance_id}",
        status_code=303,
    )


@router.post("/sau-phien/bien-ban-dau-gia/{instance_id}/dong-bo-dien-bien")
async def auction_minutes_sync_progression(
    request: Request,
    instance_id: int,
    fields_json: str = Form("{}"),
):
    token = await _token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "Chưa đăng nhập."}, status_code=401)
    try:
        fields = json.loads(fields_json or "{}")
    except json.JSONDecodeError:
        fields = {}
    minutes = dict((fields.get("minutes") or {}))
    session_id = minutes.get("session_id")
    if not session_id:
        return JSONResponse(
            {"ok": False, "error": "Chưa chọn phiên đấu giá để đồng bộ diễn biến."},
            status_code=400,
        )
    try:
        prog = await build_session_progress_data(token, int(session_id))
    except Exception as e:
        return JSONResponse({"ok": False, "error": _err_msg(e)}, status_code=502)

    minutes = _merge_progression_into_minutes(minutes, prog)
    fields["minutes"] = minutes
    try:
        await update_instance(token, instance_id, {"fields": fields})
    except Exception as e:
        return JSONResponse({"ok": False, "error": _err_msg(e)}, status_code=502)

    err = prog.get("error")
    return JSONResponse(
        {
            "ok": True,
            "minutes": minutes,
            "warning": (err.get("message") if isinstance(err, dict) else err) if err else None,
        }
    )


@router.post("/sau-phien/bien-ban-dau-gia/{instance_id}/preview", response_class=HTMLResponse)
async def auction_minutes_preview(
    request: Request,
    instance_id: int,
    fields_json: str = Form("{}"),
):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    try:
        fields = json.loads(fields_json or "{}")
    except json.JSONDecodeError:
        fields = {}
    try:
        html, _, _, _ = await _render_auction_minutes(
            request,
            token,
            instance_id,
            cc,
            fields_override=fields,
            for_preview=True,
        )
    except Exception as e:
        return HTMLResponse(f"<pre>Preview error: {_err_msg(e)}</pre>", status_code=500)
    return HTMLResponse(html)


@router.get("/sau-phien/bien-ban-dau-gia/{instance_id}/tai-html")
async def auction_minutes_download_html(request: Request, instance_id: int):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    try:
        html, inst, _, _ = await _render_auction_minutes(
            request, token, instance_id, cc, for_download=True
        )
    except Exception as e:
        return HTMLResponse(f"Error: {_err_msg(e)}", status_code=500)
    fname = download_filename(inst, "html")
    return Response(
        content=html.encode("utf-8"),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": attachment_content_disposition(fname)},
    )


@router.get("/sau-phien/bien-ban-dau-gia/{instance_id}/tai-pdf")
async def auction_minutes_download_pdf(request: Request, instance_id: int):
    token = await _token(request)
    me = await fetch_me(token)
    cc = company_code_from_me(me)
    try:
        html, inst, _, _ = await _render_auction_minutes(
            request, token, instance_id, cc, for_download=True
        )
        pdf = html_to_pdf_bytes(html)
    except Exception as e:
        return HTMLResponse(f"Error: {_err_msg(e)}", status_code=500)
    fname = download_filename(inst, "pdf")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": attachment_content_disposition(fname)},
    )
