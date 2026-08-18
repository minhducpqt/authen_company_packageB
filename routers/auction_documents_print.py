# routers/auction_documents_print.py  (Service B - Admin Portal)
from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional, List, Tuple

import httpx
from fastapi import APIRouter, Request, Path, Query
from fastapi.responses import HTMLResponse, Response

from utils.templates import templates
from utils.auth import get_access_token, fetch_me
from utils.document_templates.registry import DocKind, company_code_from_me, resolve_template

router = APIRouter(tags=["auction_sessions:documents_print"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824").rstrip("/")

# Optional: header org name/note in print template
ORG_NAME = (os.getenv("AUCTION_ORG_NAME", "").strip() or os.getenv("ORG_NAME", "").strip())
ORG_NOTE = (os.getenv("AUCTION_ORG_NOTE", "").strip() or os.getenv("ORG_NOTE", "").strip())

# =========================================================
# Logging helpers (mask sensitive)
# =========================================================
_SENSITIVE_KEYS = {"phone", "cccd", "token", "access_token", "authorization", "cookie"}


def _log(msg: str) -> None:
    print(f"[AUCTION_DOCS_PRINT_B] {msg}")


def _mask(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k and str(k).lower() in _SENSITIVE_KEYS:
                out[k] = "***"
            else:
                out[k] = _mask(v)
        return out
    if isinstance(obj, list):
        return [_mask(x) for x in obj]
    return obj


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    try:
        return str(v)
    except Exception:
        return ""


def _yob_from_cccd(cccd: Any) -> str:
    """
    CCCD 12 số: char index 3 = thế kỷ+giới tính; index 4-5 = YY.
    Same rule as attendance_public_notice template.
    """
    t = _to_str(cccd).strip()
    if len(t) < 6 or not t.isdigit():
        return ""
    g = t[3]
    try:
        yy = int(t[4:6])
    except Exception:
        return ""
    if g in ("0", "1"):
        base = 1900
    elif g in ("2", "3"):
        base = 2000
    elif g in ("4", "5"):
        base = 2100
    elif g in ("6", "7"):
        base = 2200
    elif g in ("8", "9"):
        base = 2300
    else:
        base = 1900
    y = base + yy
    if 1900 <= y <= 2100:
        return str(y)
    return ""


def _format_name_with_yob(full_name: str, yob: str) -> str:
    name = (full_name or "").strip()
    y = (yob or "").strip()
    if name and y:
        return f"{name} - {y}"
    return name


async def _a_get_json(
    path: str,
    token: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 60.0,
) -> Tuple[int, Dict[str, Any]]:
    """
    GET JSON from Service A with Bearer token.
    Returns: (status_code, json_dict)
    """
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    _log(f"→ GET(A) {url} params={_mask(params or {})}")

    async with httpx.AsyncClient(timeout=timeout) as c:
        try:
            r = await c.get(url, headers=headers, params=params or {})
        except Exception as e:
            _log(f"← EXC(A) {url} error={e}")
            return 599, {"detail": str(e)}

    try:
        js = r.json()
    except Exception:
        js = {"detail": (r.text or "")[:800]}

    _log(f"← {r.status_code}(A) {url} json_keys={list(js.keys()) if isinstance(js, dict) else type(js)}")
    return r.status_code, (js if isinstance(js, dict) else {"data": js})


def _detect_registration_mode(ui: Dict[str, Any]) -> str:
    for lot in (ui or {}).get("lots") or []:
        for p in lot.get("participants") or []:
            extras = p.get("extras") if isinstance(p.get("extras"), dict) else {}
            ga = extras.get("group_auction") if isinstance(extras, dict) else {}
            if isinstance(ga, dict) and ga.get("registration_mode"):
                return str(ga["registration_mode"]).upper()
    return "NORMAL"


def _build_print_items(attendance_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert attendance rows into template-friendly items.
    attendance row sample:
      {
        "customer_id": ...,
        "stt": ...,
        "customer": {...snapshot...},
        "refund_bank_accounts": {...} or null,
        "lot_count": n
      }
    """
    out: List[Dict[str, Any]] = []
    for r in attendance_rows or []:
        cust = r.get("customer") if isinstance(r.get("customer"), dict) else {}
        refund = r.get("refund_bank_accounts") if isinstance(r.get("refund_bank_accounts"), dict) else {}

        full_name = _to_str(
            cust.get("customer_full_name") or cust.get("full_name") or cust.get("name")
        ).strip()

        address = _to_str(cust.get("address") or cust.get("address_short") or "").strip()
        cccd = _to_str(cust.get("cccd") or "").strip()
        phone = _to_str(cust.get("phone") or "").strip()
        # Năm sinh: chỉ suy từ CCCD (đã có sẵn trên snapshot / điểm danh)
        yob = _yob_from_cccd(cccd)

        bank_short = _to_str(
            refund.get("bank_shortname")
            or refund.get("bank_name")
            or refund.get("bank_code")
            or ""
        ).strip()

        acc_no = _to_str(refund.get("account_number") or refund.get("account_no") or "").strip()
        acc_name = _to_str(refund.get("account_name") or "").strip()

        out.append(
            {
                "stt": r.get("stt"),
                "customer_full_name": full_name,
                "display_name": _format_name_with_yob(full_name, yob),
                "yob": yob,
                "address_short": address,
                "cccd": cccd,
                "phone": phone,
                "refund_bank_shortname": bank_short,
                "refund_account_no": acc_no,
                "refund_account_name": acc_name,
                "lot_count": r.get("lot_count") or 0,
            }
        )
    return out


def _aggregate_attendance_from_round_ui(
    ui: Dict[str, Any],
    *,
    registration_mode: str = "NORMAL",
) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Build attendance aggregated by customer_id from round UI payload (Service A).
    Returns: (attendance_rows_sorted, lot_count, customer_count)
    """
    is_group = (registration_mode or "").upper() == "GROUP_AUCTION"
    lots = (ui or {}).get("lots") or []
    lot_count = len(lots)

    by_cid: Dict[int, Dict[str, Any]] = {}
    lotset_by_cid: Dict[int, set] = {}

    for lot in lots:
        lot_id = lot.get("lot_id")
        parts = lot.get("participants") or []
        for p in parts:
            cid_raw = p.get("customer_id")
            if cid_raw is None:
                continue
            try:
                cid = int(cid_raw)
                if cid <= 0:
                    continue
            except Exception:
                continue

            if cid not in by_cid:
                by_cid[cid] = {
                    "customer_id": cid,
                    "stt": p.get("stt"),
                    "customer": None,
                    "refund_bank_accounts": None,
                }
                lotset_by_cid[cid] = set()

            # distinct lot count
            try:
                if lot_id is not None:
                    lotset_by_cid[cid].add(int(lot_id))
            except Exception:
                pass

            # customer snapshot priority: p.customer_snapshot OR p.extras.snapshot
            snap = p.get("customer_snapshot")
            if snap is None:
                extras = p.get("extras") if isinstance(p.get("extras"), dict) else None
                if extras and isinstance(extras.get("snapshot"), dict):
                    snap = extras.get("snapshot")

            if by_cid[cid]["customer"] is None and isinstance(snap, dict):
                by_cid[cid]["customer"] = snap

            # refund snapshot: p.extras.refund_bank_accounts (first seen)
            if by_cid[cid]["refund_bank_accounts"] is None:
                extras = p.get("extras") if isinstance(p.get("extras"), dict) else None
                if extras is not None:
                    rba = extras.get("refund_bank_accounts")
                    if rba is not None:
                        by_cid[cid]["refund_bank_accounts"] = rba

            if is_group and by_cid[cid].get("deposit_lot_count") is None:
                extras = p.get("extras") if isinstance(p.get("extras"), dict) else None
                ga = (extras or {}).get("group_auction") if isinstance(extras, dict) else None
                if isinstance(ga, dict) and ga.get("customer_deposit_lot_count") is not None:
                    try:
                        by_cid[cid]["deposit_lot_count"] = int(ga["customer_deposit_lot_count"])
                    except Exception:
                        pass

            # stt: keep smallest
            stt0 = by_cid[cid].get("stt")
            stt1 = p.get("stt")
            try:
                if stt0 is None and stt1 is not None:
                    by_cid[cid]["stt"] = int(stt1)
                elif stt0 is not None and stt1 is not None:
                    by_cid[cid]["stt"] = min(int(stt0), int(stt1))
            except Exception:
                pass

    data: List[Dict[str, Any]] = []
    for cid, item in by_cid.items():
        if is_group and item.get("deposit_lot_count") is not None:
            item["lot_count"] = int(item["deposit_lot_count"])
        else:
            lots_of_c = lotset_by_cid.get(cid) or set()
            item["lot_count"] = len(lots_of_c)
        data.append(item)

    def _sort_key(x: Dict[str, Any]):
        stt = x.get("stt")
        try:
            return (0, int(stt), int(x.get("customer_id") or 0))
        except Exception:
            return (1, 10**18, int(x.get("customer_id") or 0))

    data.sort(key=_sort_key)
    return data, lot_count, len(data)


def _stt_width(items: List[Dict[str, Any]]) -> int:
    """Pad width: 2 if max STT < 100, else 3 (4+ left as-is via zfill)."""
    mx = 0
    for it in items or []:
        try:
            mx = max(mx, int(it.get("stt") or 0))
        except Exception:
            continue
    return 2 if mx < 100 else 3


def _format_stt_display(stt: Any, width: int) -> str:
    if stt is None or stt == "":
        return ""
    try:
        n = int(stt)
        if n < 0:
            return str(stt)
        return str(n).zfill(width)
    except Exception:
        return _to_str(stt).strip()


def _build_seat_label_pages(
    items: List[Dict[str, Any]],
    *,
    per_page: int = 6,
) -> Tuple[List[List[Dict[str, Any]]], int]:
    """
    Chunk attendance print items into A4 pages (each page has exactly `per_page` slots).
    Empty trailing slots keep board cut layout; empty dicts mark blanks.
    Returns: (pages, stt_width)
    """
    n = max(1, int(per_page or 6))
    cleaned: List[Dict[str, Any]] = []
    for it in items or []:
        stt = it.get("stt")
        if stt is None or stt == "":
            continue
        cleaned.append(it)

    width = _stt_width(cleaned)
    labels: List[Dict[str, Any]] = []
    for it in cleaned:
        name = _to_str(it.get("customer_full_name") or "").strip()
        yob = _to_str(it.get("yob") or "").strip()
        display = _to_str(it.get("display_name") or "").strip() or _format_name_with_yob(name, yob)
        labels.append(
            {
                "stt": it.get("stt"),
                "stt_display": _format_stt_display(it.get("stt"), width),
                "customer_full_name": name,
                "yob": yob,
                "display_name": display,
            }
        )

    if not labels:
        # one empty page of blanks for stable template
        return [[{} for _ in range(n)]], width

    pages: List[List[Dict[str, Any]]] = []
    for i in range(0, len(labels), n):
        chunk = labels[i : i + n]
        while len(chunk) < n:
            chunk.append({})
        pages.append(chunk)
    return pages, width


async def _load_session_attendance_context(
    token: str,
    session_id: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Shared load path for attendance prints.
    Returns: (session_out, items, project, stats, error)
    """
    error: Optional[Dict[str, Any]] = None

    st_s, sess = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}", token, None, timeout=60.0
    )
    if st_s != 200 or not isinstance(sess, dict):
        error = {"message": f"Không tải được phiên đấu (status={st_s})", "body": sess}
        sess_data: Dict[str, Any] = {"id": session_id}
    else:
        sess_data = (sess.get("data") or sess) if isinstance(sess, dict) else {"id": session_id}

    project_name = sess_data.get("project_name") or sess_data.get("p_project_name") or ""
    project_code = sess_data.get("project_code") or sess_data.get("p_project_code") or ""
    registration_mode = "NORMAL"

    round_no = 1
    st_c, cur = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/current", token, None, timeout=60.0
    )
    if st_c == 200 and isinstance(cur, dict):
        try:
            rn = int(cur.get("current_round_no") or 0)
            round_no = rn if rn > 0 else 1
        except Exception:
            round_no = 1
    else:
        if not error:
            error = {"message": f"Không tải được vòng hiện tại (status={st_c})", "body": cur}

    attendance_rows: List[Dict[str, Any]] = []
    lot_count = 0
    customer_count = 0

    st_ui, ui = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}/ui",
        token,
        None,
        timeout=60.0,
    )
    if st_ui == 200 and isinstance(ui, dict):
        reg_mode = _detect_registration_mode(ui)
        registration_mode = reg_mode
        attendance_rows, lot_count, customer_count = _aggregate_attendance_from_round_ui(
            ui, registration_mode=reg_mode
        )
    else:
        if not error:
            error = {"message": f"Không tải được dữ liệu vòng (status={st_ui})", "body": ui}

    session_out = {
        "id": sess_data.get("id") or session_id,
        "name": sess_data.get("name"),
        "status": sess_data.get("status"),
        "auction_date": sess_data.get("auction_date"),
        "location": sess_data.get("location"),
        "province": sess_data.get("province"),
        "district": sess_data.get("district"),
        "venue": sess_data.get("venue"),
        "note": sess_data.get("note"),
        "project_id": sess_data.get("project_id"),
        "project_code": project_code,
        "project_name": project_name,
        "lot_count": lot_count,
        "customer_count": customer_count,
        "round_no": int(round_no),
        "registration_mode": registration_mode,
        "company_code": sess_data.get("company_code"),
    }
    project = {"name": project_name or project_code or "", "project_code": project_code or ""}
    stats = {"total_lots": lot_count or 0, "total_customers": customer_count or 0}
    items = _build_print_items(attendance_rows)
    return session_out, items, project, stats, error


# =========================================================
# PRINT: Attendance list (A4)
# =========================================================
@router.get(
    "/auction/sessions/{session_id}/documents/attendance/print",
    response_class=HTMLResponse,
)
async def print_attendance_list(
    request: Request,
    session_id: int = Path(..., ge=1),
    title: Optional[str] = Query(None),
    autoprint: int = Query(0, ge=0, le=1),
):
    """
    In danh sách điểm danh người tham gia đấu giá (A4).
    ✅ GỌI THẲNG SERVICE A (không gọi nội bộ B nữa)
    Flow:
      1) GET A: /sessions/{id}
      2) GET A: /sessions/{id}/current  -> round_no
      3) GET A: /sessions/{id}/rounds/{round_no}/ui
      4) aggregate attendance from UI
    """
    token = get_access_token(request)
    if not token:
        return templates.TemplateResponse(
            "pages/error.html",
            {
                "request": request,
                "title": "Chưa đăng nhập",
                "message": "Vui lòng đăng nhập lại.",
            },
            status_code=401,
        )

    error: Optional[Dict[str, Any]] = None

    # 1) session detail
    st_s, sess = await _a_get_json(f"/api/v1/auction-sessions/sessions/{session_id}", token, None, timeout=60.0)
    if st_s != 200 or not isinstance(sess, dict):
        error = {"message": f"Không tải được phiên đấu (status={st_s})", "body": sess}
        sess_data: Dict[str, Any] = {"id": session_id}
    else:
        sess_data = (sess.get("data") or sess) if isinstance(sess, dict) else {"id": session_id}

    project_name = sess_data.get("project_name") or sess_data.get("p_project_name") or ""
    project_code = sess_data.get("project_code") or sess_data.get("p_project_code") or ""
    registration_mode = "NORMAL"

    # 2) current round
    round_no = 1
    st_c, cur = await _a_get_json(f"/api/v1/auction-sessions/sessions/{session_id}/current", token, None, timeout=60.0)
    if st_c == 200 and isinstance(cur, dict):
        try:
            rn = int(cur.get("current_round_no") or 0)
            round_no = rn if rn > 0 else 1
        except Exception:
            round_no = 1
    else:
        # không chết ở đây, cứ fallback round 1
        if not error:
            error = {"message": f"Không tải được vòng hiện tại (status={st_c})", "body": cur}

    # 3) round UI
    attendance_rows: List[Dict[str, Any]] = []
    lot_count = 0
    customer_count = 0

    st_ui, ui = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}/ui",
        token,
        None,
        timeout=60.0,
    )
    if st_ui == 200 and isinstance(ui, dict):
        reg_mode = _detect_registration_mode(ui)
        registration_mode = reg_mode
        attendance_rows, lot_count, customer_count = _aggregate_attendance_from_round_ui(
            ui, registration_mode=reg_mode
        )
    else:
        if not error:
            error = {"message": f"Không tải được dữ liệu vòng (status={st_ui})", "body": ui}

    # Build template variables
    session_out = {
        "id": sess_data.get("id") or session_id,
        "name": sess_data.get("name"),
        "status": sess_data.get("status"),
        "auction_date": sess_data.get("auction_date"),
        "location": sess_data.get("location"),
        "province": sess_data.get("province"),
        "district": sess_data.get("district"),
        "venue": sess_data.get("venue"),
        "note": sess_data.get("note"),
        "project_id": sess_data.get("project_id"),
        "project_code": project_code,
        "project_name": project_name,
        "lot_count": lot_count,
        "customer_count": customer_count,
        "round_no": int(round_no),
        "registration_mode": registration_mode,
    }

    project = {"name": project_name or project_code or "", "project_code": project_code or ""}
    stats = {"total_lots": lot_count or 0, "total_customers": customer_count or 0}
    items = _build_print_items(attendance_rows)

    # optional debug payload if you still want
    attendance_payload = {"ok": True, "session": session_out, "data": attendance_rows}

    token_cc = get_access_token(request)
    me = await fetch_me(token_cc) if token_cc else None
    cc = company_code_from_me(me) or str(sess_data.get("company_code") or "").strip().lower()
    attendance_tpl = resolve_template(cc, DocKind.ATTENDANCE_SESSION)

    return templates.TemplateResponse(
        attendance_tpl,
        {
            "request": request,
            "title": title or "Danh sách điểm danh người tham gia đấu giá",
            "session_id": session_id,

            # raw payload (optional debug)
            "attendance": attendance_payload,

            # template variables
            "session": session_out,
            "project": project,
            "stats": stats,
            "items": items,

            # org header
            "org_name": ORG_NAME,
            "org_note": ORG_NOTE,

            # auto print flag for template JS
            "autoprint": int(autoprint),

            # error payload
            "error": error,
        },
    )


# =========================================================
# PRINT: Public notice (A4) — STT lookup board (NO SIGNATURE)
#   - Data source & flow: identical to attendance_print above
#   - Template: pages/documents/default/attendance_public_notice.html
# =========================================================
@router.get(
    "/auction/sessions/{session_id}/documents/attendance/public-notice",
    response_class=HTMLResponse,
)
async def print_attendance_public_notice(
    request: Request,
    session_id: int = Path(..., ge=1),
    title: Optional[str] = Query(None),
    autoprint: int = Query(0, ge=0, le=1),
):
    """
    In danh sách công khai để dán bảng tin (khách tra cứu STT).
    ✅ GỌI THẲNG SERVICE A (y hệt attendance/print)
    Flow:
      1) GET A: /sessions/{id}
      2) GET A: /sessions/{id}/current  -> round_no
      3) GET A: /sessions/{id}/rounds/{round_no}/ui
      4) aggregate attendance from UI
    """
    token = get_access_token(request)
    if not token:
        return templates.TemplateResponse(
            "pages/error.html",
            {
                "request": request,
                "title": "Chưa đăng nhập",
                "message": "Vui lòng đăng nhập lại.",
            },
            status_code=401,
        )

    error: Optional[Dict[str, Any]] = None

    # 1) session detail
    st_s, sess = await _a_get_json(f"/api/v1/auction-sessions/sessions/{session_id}", token, None, timeout=60.0)
    if st_s != 200 or not isinstance(sess, dict):
        error = {"message": f"Không tải được phiên đấu (status={st_s})", "body": sess}
        sess_data: Dict[str, Any] = {"id": session_id}
    else:
        sess_data = (sess.get("data") or sess) if isinstance(sess, dict) else {"id": session_id}

    project_name = sess_data.get("project_name") or sess_data.get("p_project_name") or ""
    project_code = sess_data.get("project_code") or sess_data.get("p_project_code") or ""
    registration_mode = "NORMAL"

    # 2) current round
    round_no = 1
    st_c, cur = await _a_get_json(f"/api/v1/auction-sessions/sessions/{session_id}/current", token, None, timeout=60.0)
    if st_c == 200 and isinstance(cur, dict):
        try:
            rn = int(cur.get("current_round_no") or 0)
            round_no = rn if rn > 0 else 1
        except Exception:
            round_no = 1
    else:
        if not error:
            error = {"message": f"Không tải được vòng hiện tại (status={st_c})", "body": cur}

    # 3) round UI
    attendance_rows: List[Dict[str, Any]] = []
    lot_count = 0
    customer_count = 0

    st_ui, ui = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}/ui",
        token,
        None,
        timeout=60.0,
    )
    if st_ui == 200 and isinstance(ui, dict):
        reg_mode = _detect_registration_mode(ui)
        registration_mode = reg_mode
        attendance_rows, lot_count, customer_count = _aggregate_attendance_from_round_ui(
            ui, registration_mode=reg_mode
        )
    else:
        if not error:
            error = {"message": f"Không tải được dữ liệu vòng (status={st_ui})", "body": ui}

    # Build template variables (same structure as attendance/print)
    session_out = {
        "id": sess_data.get("id") or session_id,
        "name": sess_data.get("name"),
        "status": sess_data.get("status"),
        "auction_date": sess_data.get("auction_date"),
        "location": sess_data.get("location"),
        "province": sess_data.get("province"),
        "district": sess_data.get("district"),
        "venue": sess_data.get("venue"),
        "note": sess_data.get("note"),
        "project_id": sess_data.get("project_id"),
        "project_code": project_code,
        "project_name": project_name,
        "lot_count": lot_count,
        "customer_count": customer_count,
        "round_no": int(round_no),
        "registration_mode": registration_mode,
    }

    project = {"name": project_name or project_code or "", "project_code": project_code or ""}
    stats = {"total_lots": lot_count or 0, "total_customers": customer_count or 0}

    # Keep consistency: provide both rows (for template) and items (optional)
    items = _build_print_items(attendance_rows)

    # raw payload (optional debug)
    attendance_payload = {"ok": True, "session": session_out, "data": attendance_rows}

    token_cc = get_access_token(request)
    me = await fetch_me(token_cc) if token_cc else None
    cc = company_code_from_me(me) or str(sess_data.get("company_code") or "").strip().lower()
    notice_tpl = resolve_template(cc, DocKind.ATTENDANCE_PUBLIC_NOTICE)

    return templates.TemplateResponse(
        notice_tpl,
        {
            "request": request,
            "title": title or "Danh sách STT tham dự đấu giá",
            "session_id": session_id,

            # raw payload (optional debug)
            "attendance": attendance_payload,

            # template variables
            "session": session_out,
            "project": project,
            "stats": stats,

            # IMPORTANT: the public template consumes `rows` (or attendance.data)
            "rows": attendance_rows,
            "items": items,

            # org header (kept for consistency)
            "org_name": ORG_NAME,
            "org_note": ORG_NOTE,

            # auto print flag for template JS
            "autoprint": int(autoprint),

            # error payload
            "error": error,
        },
    )


# =========================================================
# PRINT: Seat STT labels (A4 — 2×3) — dán sau ghế
#   - Cùng nguồn danh sách điểm danh phiên (aggregate round UI)
#   - 6 nhãn / trang; trang lẻ pad ô trống
# =========================================================
@router.get(
    "/auction/sessions/{session_id}/documents/attendance/seat-labels",
    response_class=HTMLResponse,
)
async def print_attendance_seat_labels(
    request: Request,
    session_id: int = Path(..., ge=1),
    title: Optional[str] = Query(None),
    autoprint: int = Query(0, ge=0, le=1),
):
    """In nhãn STT dán ghế (A4, 6 ô). Data = danh sách điểm danh hiện tại."""
    token = get_access_token(request)
    if not token:
        return templates.TemplateResponse(
            "pages/error.html",
            {
                "request": request,
                "title": "Chưa đăng nhập",
                "message": "Vui lòng đăng nhập lại.",
            },
            status_code=401,
        )

    session_out, items, project, stats, error = await _load_session_attendance_context(
        token, session_id
    )
    pages, stt_width = _build_seat_label_pages(items, per_page=6)

    token_cc = get_access_token(request)
    me = await fetch_me(token_cc) if token_cc else None
    cc = company_code_from_me(me) or str(session_out.get("company_code") or "").strip().lower()
    seat_tpl = resolve_template(cc, DocKind.ATTENDANCE_SEAT_LABELS)

    return templates.TemplateResponse(
        seat_tpl,
        {
            "request": request,
            "title": title or "Nhãn STT dán ghế",
            "session_id": session_id,
            "session": session_out,
            "project": project,
            "stats": stats,
            "items": items,
            "pages": pages,
            "per_page": 6,
            "stt_width": stt_width,
            "org_name": ORG_NAME,
            "org_note": ORG_NOTE,
            "autoprint": int(autoprint),
            "error": error,
        },
    )


# =========================================================
# PRINT: Danh sách ký xác nhận trúng đấu giá (A4 landscape)
#   - 1 row / lô (các lô trong phiên, vòng 1)
#   - Giá khởi điểm = start_price vòng 1
#   - Họ tên / CCCD / Giá trúng / Chữ ký: để trống (điền tay)
# =========================================================


def _fmt_vnd_dot(v: Any) -> str:
    if v is None or v == "":
        return ""
    try:
        n = int(round(float(v)))
    except Exception:
        return _to_str(v)
    if n < 0:
        return "-" + f"{abs(n):,}".replace(",", ".")
    return f"{n:,}".replace(",", ".")


def _normalize_auction_mode(raw: Any) -> str:
    m = _to_str(raw).strip().upper()
    if m in ("PER_SQM", "PER_M2", "PER_M", "M2", "SQM"):
        return "PER_SQM"
    if m in ("PER_LOT", "LOT", "PER_LO"):
        return "PER_LOT"
    return "PER_LOT"


def _auction_mode_unit_label(mode: str) -> str:
    return "m2" if _normalize_auction_mode(mode) == "PER_SQM" else "lô"


def _lot_natural_sort_key(code: str) -> Tuple:
    s = (code or "").strip()
    parts = re.split(r"(\d+)", s)
    out: List[Any] = []
    for p in parts:
        if not p:
            continue
        if p.isdigit():
            try:
                out.append((0, int(p)))
            except Exception:
                out.append((1, p.lower()))
        else:
            out.append((1, p.lower()))
    return tuple(out) if out else ((1, s.lower()),)


def _fmt_vn_date_long(auction_date: Any) -> Dict[str, str]:
    """
    Parse YYYY-MM-DD (or ISO datetime) → day/month/year strings.
    """
    s = _to_str(auction_date).strip()
    y = m = d = ""
    if s:
        # "2026-08-12" or "2026-08-12T00:00:00..."
        m0 = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
        if m0:
            y, m, d = m0.group(1), m0.group(2), m0.group(3)
        else:
            m1 = re.match(r"^(\d{2})/(\d{2})/(\d{4})", s)
            if m1:
                d, m, y = m1.group(1), m1.group(2), m1.group(3)
    return {
        "day": str(int(d)) if d.isdigit() else d,
        "month": str(int(m)) if m.isdigit() else m,
        "year": y,
    }


def _extract_lot_snapshot(lot: Dict[str, Any]) -> Dict[str, Any]:
    snap = lot.get("lot_snapshot")
    if isinstance(snap, dict):
        return snap
    extras = lot.get("extras") if isinstance(lot.get("extras"), dict) else {}
    if isinstance(extras.get("snapshot"), dict):
        return extras["snapshot"]
    return {}


def _build_winner_sign_rows(ui: Dict[str, Any], *, auction_mode: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for lot in (ui or {}).get("lots") or []:
        if not isinstance(lot, dict):
            continue
        snap = _extract_lot_snapshot(lot)
        lot_code = _to_str(
            lot.get("lot_code") or snap.get("lot_code") or lot.get("lot_name") or ""
        ).strip()
        if not lot_code and lot.get("lot_id") is not None:
            lot_code = f"#{lot.get('lot_id')}"

        sp = lot.get("start_price_vnd")
        if sp is None:
            sp = snap.get("start_price_vnd")
        if sp is None:
            sp = snap.get("starting_price_vnd")

        mode = _normalize_auction_mode(
            lot.get("auction_mode")
            or snap.get("auction_mode")
            or snap.get("bid_price_unit")
            or auction_mode
        )

        rows.append(
            {
                "lot_id": lot.get("lot_id") or lot.get("id"),
                "lot_code": lot_code,
                "start_price_vnd": sp,
                "start_price_display": _fmt_vnd_dot(sp),
                "auction_mode": mode,
            }
        )

    rows.sort(
        key=lambda r: (
            _lot_natural_sort_key(_to_str(r.get("lot_code"))),
            int(r.get("lot_id") or 0) if str(r.get("lot_id") or "").isdigit() else 0,
        )
    )
    for i, r in enumerate(rows, start=1):
        r["stt"] = i
    return rows


def _chunk_pages(
    items: List[Dict[str, Any]],
    *,
    per_page: int = 10,
    first_page: Optional[int] = None,
) -> List[List[Dict[str, Any]]]:
    """
    Chia trang: trang đầu có thể khác (để chừa chỗ header/title),
    các trang sau lấy `per_page` dòng.
    """
    n = max(1, int(per_page or 10))
    first_n = max(1, int(first_page if first_page is not None else n))
    data = list(items or [])
    if not data:
        return [[]]
    pages: List[List[Dict[str, Any]]] = [data[:first_n]]
    rest = data[first_n:]
    for i in range(0, len(rest), n):
        pages.append(rest[i : i + n])
    return pages


@router.get(
    "/auction/sessions/{session_id}/documents/attendance/winner-sign-list",
    response_class=HTMLResponse,
)
async def print_winner_sign_list(
    request: Request,
    session_id: int = Path(..., ge=1),
    title: Optional[str] = Query(None),
    autoprint: int = Query(0, ge=0, le=1),
):
    """
    In danh sách ký xác nhận trúng đấu giá (A4 ngang).
    Dòng = các lô trong phiên (nguồn vòng 1); giá khởi điểm = vòng 1.
    """
    token = get_access_token(request)
    if not token:
        return templates.TemplateResponse(
            "pages/error.html",
            {
                "request": request,
                "title": "Chưa đăng nhập",
                "message": "Vui lòng đăng nhập lại.",
            },
            status_code=401,
        )

    error: Optional[Dict[str, Any]] = None

    st_s, sess = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}", token, None, timeout=60.0
    )
    if st_s != 200 or not isinstance(sess, dict):
        error = {"message": f"Không tải được phiên đấu (status={st_s})", "body": sess}
        sess_data: Dict[str, Any] = {"id": session_id}
    else:
        sess_data = (sess.get("data") or sess) if isinstance(sess, dict) else {"id": session_id}

    project_id = sess_data.get("project_id")
    project_name = sess_data.get("project_name") or sess_data.get("p_project_name") or ""
    project_code = sess_data.get("project_code") or sess_data.get("p_project_code") or ""
    company_code = _to_str(sess_data.get("company_code") or "").strip()
    company_name = ""
    auction_mode = "PER_LOT"
    auction_mode_from_project = False

    # Project: title + auction_mode
    if project_id:
        st_p, prj = await _a_get_json(
            f"/api/v1/projects/{project_id}", token, None, timeout=30.0
        )
        if st_p == 200 and isinstance(prj, dict):
            pdata = (prj.get("data") if isinstance(prj.get("data"), dict) else prj) or {}
            if pdata.get("name"):
                project_name = pdata.get("name") or project_name
            if pdata.get("project_code"):
                project_code = pdata.get("project_code") or project_code
            if pdata.get("company_code") and not company_code:
                company_code = _to_str(pdata.get("company_code")).strip()
            if pdata.get("auction_mode") is not None and str(pdata.get("auction_mode")).strip():
                auction_mode = _normalize_auction_mode(pdata.get("auction_mode"))
                auction_mode_from_project = True
        elif not error:
            error = {"message": f"Không tải được dự án (status={st_p})", "body": prj}

    # Company name (best-effort via display context)
    st_d, disp = await _a_get_json(
        f"/api/v1/auction-sessions/display/sessions/{session_id}",
        token,
        {"round_no": 1},
        timeout=30.0,
    )
    if st_d == 200 and isinstance(disp, dict):
        ctx = disp.get("context") if isinstance(disp.get("context"), dict) else {}
        company_name = _to_str(
            disp.get("company_name") or ctx.get("company_name") or ""
        ).strip()
        if not project_name:
            project_name = _to_str(
                disp.get("project_name") or ctx.get("project_name") or ""
            ).strip()
        if not company_code:
            company_code = _to_str(
                disp.get("company_code") or ctx.get("company_code") or ""
            ).strip()

    if not company_name:
        company_name = ORG_NAME or ""

    # Round 1 UI → lots + starting prices (full list of lots in session)
    rows: List[Dict[str, Any]] = []
    st_ui, ui = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/1/ui",
        token,
        None,
        timeout=60.0,
    )
    if st_ui == 200 and isinstance(ui, dict):
        rows = _build_winner_sign_rows(ui, auction_mode=auction_mode)
        if not auction_mode_from_project:
            modes = [r.get("auction_mode") for r in rows if r.get("auction_mode")]
            if modes:
                sqm_n = sum(1 for m in modes if m == "PER_SQM")
                auction_mode = "PER_SQM" if sqm_n > len(modes) / 2 else _normalize_auction_mode(modes[0])
    else:
        if not error:
            error = {
                "message": f"Không tải được dữ liệu vòng 1 (status={st_ui})",
                "body": ui,
            }

    unit = _auction_mode_unit_label(auction_mode)
    date_parts = _fmt_vn_date_long(sess_data.get("auction_date"))
    place = (
        _to_str(sess_data.get("province") or "").strip()
        or _to_str(sess_data.get("district") or "").strip()
        or _to_str(sess_data.get("location") or "").strip()
        or ""
    )
    venue = (
        _to_str(sess_data.get("venue") or "").strip()
        or _to_str(sess_data.get("location") or "").strip()
        or ""
    )

    # "Ninh Bình, ngày 12 tháng 8 năm 2026"
    date_line_bits = []
    if place:
        date_line_bits.append(place)
    if date_parts.get("day") and date_parts.get("month") and date_parts.get("year"):
        date_clause = (
            f"ngày {date_parts['day']} tháng {date_parts['month']} năm {date_parts['year']}"
        )
        if date_line_bits:
            date_line_bits.append(date_clause)
        else:
            date_line_bits.append(date_clause)
    date_line = ", ".join(date_line_bits) if date_line_bits else ""

    session_out = {
        "id": sess_data.get("id") or session_id,
        "name": sess_data.get("name"),
        "status": sess_data.get("status"),
        "auction_date": sess_data.get("auction_date"),
        "location": sess_data.get("location"),
        "province": sess_data.get("province"),
        "district": sess_data.get("district"),
        "venue": sess_data.get("venue"),
        "note": sess_data.get("note"),
        "project_id": project_id,
        "project_code": project_code,
        "project_name": project_name,
        "company_code": company_code,
        "company_name": company_name,
        "place": place,
        "venue_display": venue,
        "date_line": date_line,
        "auction_mode": auction_mode,
        "price_unit": unit,
    }
    project = {
        "name": project_name or project_code or "",
        "project_code": project_code or "",
        "auction_mode": auction_mode,
    }

    me = await fetch_me(token)
    cc = company_code_from_me(me) or company_code.strip().lower()
    tpl = resolve_template(cc, DocKind.WINNER_SIGN_LIST)

    per_page = 10
    # Trang 1 có header/title/địa điểm + hàng cao → 8 dòng;
    # trang sau không header → 10 dòng.
    first_page = 8
    pages = _chunk_pages(rows, per_page=per_page, first_page=first_page)

    return templates.TemplateResponse(
        tpl,
        {
            "request": request,
            "title": title or "Danh sách ký xác nhận trúng đấu giá",
            "session_id": session_id,
            "session": session_out,
            "project": project,
            "company_name": company_name,
            "org_name": company_name or ORG_NAME,
            "org_note": ORG_NOTE,
            "rows": rows,
            "pages": pages,
            "per_page": per_page,
            "first_page": first_page,
            "auction_mode": auction_mode,
            "price_unit": unit,
            "date_line": date_line,
            "venue": venue,
            "autoprint": int(autoprint),
            "error": error,
        },
    )


# =========================================================
# PRINT: Kết quả vòng đấu (A4 portrait)
# =========================================================


def _participant_snapshot(p: Dict[str, Any]) -> Dict[str, Any]:
    snap = p.get("customer_snapshot")
    if isinstance(snap, dict):
        return snap
    extras = p.get("extras") if isinstance(p.get("extras"), dict) else {}
    if isinstance(extras.get("snapshot"), dict):
        return extras["snapshot"]
    return {}


def _person_from_participant(p: Dict[str, Any]) -> Dict[str, Any]:
    snap = _participant_snapshot(p)
    return {
        "customer_id": p.get("customer_id") or snap.get("customer_id"),
        "stt": p.get("stt") or snap.get("stt"),
        "full_name": _to_str(
            snap.get("customer_full_name") or snap.get("full_name") or snap.get("name")
        ).strip(),
        "cccd": _to_str(snap.get("cccd") or "").strip(),
        "phone": _to_str(snap.get("phone") or "").strip(),
    }


def _person_by_customer_id(participants: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for p in participants or []:
        try:
            cid = int(p.get("customer_id") or 0)
        except Exception:
            continue
        if cid <= 0:
            continue
        out[cid] = _person_from_participant(p)
    return out


def _ballot_counts_for_print(
    ballot: Dict[str, Any],
    *,
    participant_count: int = 0,
) -> Tuple[Any, Any, Any, Any]:
    """
    Phát ra: luôn có (sinh từ phần mềm / số khách tham gia).
    Thu / HL / KHL: chỉ khi đã ghi DB kiểm phiếu; không có → None (—).
    """
    issued: Any = None
    if ballot:
        issued = ballot.get("issued_count")
        if issued is None:
            issued = ballot.get("issued_live")
    if issued is None and participant_count > 0:
        issued = participant_count
    elif issued is None and ballot:
        live = ballot.get("issued_live")
        if live is not None:
            issued = live

    if not ballot or not ballot.get("is_recorded"):
        return issued, None, None, None

    return (
        issued,
        ballot.get("collected_count"),
        ballot.get("valid_count"),
        ballot.get("invalid_count"),
    )


def _win_method_note(win_method: Any) -> str:
    wm = _to_str(win_method or "").strip().upper()
    if wm == "LOTTERY":
        return "Bốc thăm"
    if wm == "MANUAL":
        return "Thủ công"
    if wm == "HIGHEST":
        return "Cao nhất"
    return ""


def _status_short_label(status_kind: str, status_label: str) -> str:
    m = {
        "ok": "Trúng",
        "next": "V.trong",
        "fail": "K.thành",
        "pending": "Chưa chốt",
    }
    return m.get(status_kind, status_label)


def _price_column_labels(auction_mode: str) -> Dict[str, str]:
    unit = _auction_mode_unit_label(auction_mode)
    if unit == "m2":
        return {
            "start": "Giá KD",
            "start_unit": "VNĐ/m²",
            "highest": "Giá cao nhất",
            "highest_unit": "VNĐ/m²",
            "unit_note": "VNĐ/m²",
        }
    return {
        "start": "Giá KD",
        "start_unit": "VNĐ/lô",
        "highest": "Giá cao nhất",
        "highest_unit": "VNĐ/lô",
        "unit_note": "VNĐ/lô",
    }


def _result_status_label(
    result_type: Any,
    *,
    round_no: int = 1,
    valid_count: Any = None,
    ballot_recorded: bool = False,
) -> Tuple[str, str]:
    rt = _to_str(result_type or "PENDING").strip().upper()
    if rt == "WINNER":
        return "Đã có người trúng", "ok"
    if rt == "NEXT_ROUND":
        return "Vào vòng trong", "next"
    if rt == "NO_VALID":
        return "Đấu không thành", "fail"
    # Vòng 1: ≤1 phiếu HL (đã ghi kiểm phiếu) → coi là không thành
    if int(round_no or 0) == 1 and ballot_recorded and valid_count is not None:
        try:
            if int(valid_count) <= 1:
                return "Đấu không thành", "fail"
        except Exception:
            pass
    return "Chưa chốt", "pending"


async def _fetch_ballots_for_lots(
    token: str,
    round_lot_ids: List[int],
) -> Dict[int, Dict[str, Any]]:
    import asyncio

    async def _one(rlid: int) -> Tuple[int, Dict[str, Any]]:
        st, js = await _a_get_json(
            f"/api/v1/auction-sessions/round-lots/{rlid}/ballot-counts",
            token,
            None,
            timeout=30.0,
        )
        if st == 200 and isinstance(js, dict):
            return rlid, js
        return rlid, {}

    if not round_lot_ids:
        return {}
    pairs = await asyncio.gather(*[_one(rid) for rid in round_lot_ids])
    return {rid: data for rid, data in pairs}


def _build_round_result_rows(
    ui: Dict[str, Any],
    *,
    results_by_lot: Dict[int, Dict[str, Any]],
    ballots_by_lot: Dict[int, Dict[str, Any]],
    round_no: int = 1,
) -> List[Dict[str, Any]]:
    rn = max(1, int(round_no or 1))
    rows: List[Dict[str, Any]] = []
    for lot in (ui or {}).get("lots") or []:
        if not isinstance(lot, dict):
            continue
        snap = _extract_lot_snapshot(lot)
        lot_code = _to_str(lot.get("lot_code") or snap.get("lot_code") or "").strip()
        try:
            lot_id = int(lot.get("lot_id") or 0)
        except Exception:
            lot_id = 0
        try:
            round_lot_id = int(lot.get("id") or 0)
        except Exception:
            round_lot_id = 0

        participants = lot.get("participants") or []
        by_cid = _person_by_customer_id(participants)

        ballot = ballots_by_lot.get(round_lot_id) or {}
        ballot_recorded = bool(ballot.get("is_recorded"))
        issued, collected, valid, invalid = _ballot_counts_for_print(
            ballot,
            participant_count=len(participants),
        )

        start_price = lot.get("start_price_vnd")
        if start_price is None:
            start_price = snap.get("start_price_vnd") or snap.get("starting_price_vnd")
        highest = lot.get("highest_price_vnd")

        rt = _to_str(lot.get("result_type") or "PENDING").upper()
        status_label, status_kind = _result_status_label(
            rt,
            round_no=rn,
            valid_count=valid,
            ballot_recorded=ballot_recorded,
        )
        status_note = ""
        if rt == "WINNER":
            status_note = _win_method_note(lot.get("win_method"))

        detail_lines: List[str] = []
        winner_name = ""
        winner_cccd = ""

        res = results_by_lot.get(lot_id) if lot_id else None
        if rt == "WINNER":
            wcid = lot.get("winner_customer_id")
            w_stt = ""
            if res:
                winner_name = _to_str(res.get("winner_name") or "").strip()
                winner_cccd = _to_str(res.get("winner_cccd") or "").strip()
            if wcid is not None:
                try:
                    p = by_cid.get(int(wcid)) or {}
                    if not winner_name:
                        winner_name = p.get("full_name") or ""
                    if not winner_cccd:
                        winner_cccd = p.get("cccd") or ""
                    w_stt = p.get("stt") or ""
                except Exception:
                    pass
            if winner_name:
                line = f"• STT {w_stt} — {winner_name}" if w_stt != "" else f"• {winner_name}"
                if winner_cccd:
                    line += f" (CCCD: {winner_cccd})"
                detail_lines.append(line)
            wp = res.get("winning_price_vnd") if res else None
            if wp is not None:
                detail_lines.append(f"Giá trúng: {_fmt_vnd_dot(wp)}")
        elif rt == "NEXT_ROUND":
            nx = lot.get("next_participants") or []
            status_note = f"Tổng {len(nx)} khách"
            for np in nx:
                try:
                    cid = int(np.get("customer_id") or 0)
                except Exception:
                    cid = 0
                p = by_cid.get(cid) or {}
                stt = np.get("stt") if np.get("stt") is not None else p.get("stt")
                name = p.get("full_name") or f"#{cid}"
                cccd = p.get("cccd") or ""
                line = f"• STT {stt} — {name}" if stt != "" and stt is not None else f"• {name}"
                if cccd:
                    line += f" (CCCD: {cccd})"
                detail_lines.append(line)
            if not nx:
                detail_lines.append("(Chưa có danh sách vào vòng trong)")
        elif rt == "NO_VALID":
            detail_lines.append("Không đủ phiếu hợp lệ để tiếp tục đấu.")
        elif rn == 1 and ballot_recorded and valid is not None and int(valid) <= 1:
            detail_lines.append(f"Phiếu hợp lệ: {valid} — đấu không thành (vòng 1).")
        else:
            detail_lines.append(f"{len(participants)} người tham gia vòng này.")

        rows.append(
            {
                "lot_code": lot_code or (f"#{lot_id}" if lot_id else "—"),
                "lot_id": lot_id,
                "round_lot_id": round_lot_id,
                "issued": issued,
                "collected": collected,
                "valid": valid,
                "invalid": invalid,
                "start_price_display": _fmt_vnd_dot(start_price),
                "highest_price_display": _fmt_vnd_dot(highest) if highest is not None else "",
                "result_type": rt,
                "status_label": status_label,
                "status_short": _status_short_label(status_kind, status_label),
                "status_kind": status_kind,
                "status_note": status_note,
                "detail_lines": detail_lines,
                "detail": "\n".join(detail_lines),
                "winner_name": winner_name,
                "winner_cccd": winner_cccd,
            }
        )

    rows.sort(
        key=lambda r: (
            _lot_natural_sort_key(_to_str(r.get("lot_code"))),
            int(r.get("lot_id") or 0),
        )
    )
    for i, r in enumerate(rows, start=1):
        r["stt"] = i
    return rows


@router.get(
    "/auction/sessions/{session_id}/rounds/{round_no}/results/print",
    response_class=HTMLResponse,
)
async def print_round_results(
    request: Request,
    session_id: int = Path(..., ge=1),
    round_no: int = Path(..., ge=1),
    title: Optional[str] = Query(None),
    autoprint: int = Query(0, ge=0, le=1),
    download: Optional[str] = Query(None),
):
    """In bảng kết quả toàn vòng: kiểm phiếu, giá, trạng thái, người trúng / vào vòng trong."""
    token = get_access_token(request)
    if not token:
        return templates.TemplateResponse(
            "pages/error.html",
            {
                "request": request,
                "title": "Chưa đăng nhập",
                "message": "Vui lòng đăng nhập lại.",
            },
            status_code=401,
        )

    error: Optional[Dict[str, Any]] = None

    st_s, sess = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}", token, None, timeout=60.0
    )
    if st_s != 200 or not isinstance(sess, dict):
        error = {"message": f"Không tải được phiên đấu (status={st_s})", "body": sess}
        sess_data: Dict[str, Any] = {"id": session_id}
    else:
        sess_data = (sess.get("data") or sess) if isinstance(sess, dict) else {"id": session_id}

    project_name = sess_data.get("project_name") or sess_data.get("p_project_name") or ""
    project_code = sess_data.get("project_code") or sess_data.get("p_project_code") or ""
    project_id = sess_data.get("project_id")
    auction_mode = "PER_LOT"

    if project_id:
        st_p, prj = await _a_get_json(
            f"/api/v1/projects/{project_id}", token, None, timeout=30.0
        )
        if st_p == 200 and isinstance(prj, dict):
            pdata = (prj.get("data") if isinstance(prj.get("data"), dict) else prj) or {}
            if pdata.get("name"):
                project_name = pdata.get("name") or project_name
            if pdata.get("project_code"):
                project_code = pdata.get("project_code") or project_code
            if pdata.get("auction_mode") is not None and str(pdata.get("auction_mode")).strip():
                auction_mode = _normalize_auction_mode(pdata.get("auction_mode"))

    price_labels = _price_column_labels(auction_mode)

    st_ui, ui = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/{round_no}/ui",
        token,
        None,
        timeout=60.0,
    )
    if st_ui != 200 or not isinstance(ui, dict):
        error = error or {
            "message": f"Không tải được dữ liệu vòng {round_no} (status={st_ui})",
            "body": ui,
        }
        ui = {}

    st_res, res_js = await _a_get_json(
        f"/api/v1/auction-sessions/sessions/{session_id}/results",
        token,
        None,
        timeout=60.0,
    )
    results_by_lot: Dict[int, Dict[str, Any]] = {}
    if st_res == 200 and isinstance(res_js, dict):
        for row in (res_js.get("data") or []):
            if not isinstance(row, dict):
                continue
            try:
                lid = int(row.get("lot_id") or 0)
            except Exception:
                continue
            if lid > 0:
                results_by_lot[lid] = row
    elif not error:
        error = {"message": f"Không tải được kết quả phiên (status={st_res})", "body": res_js}

    round_lot_ids: List[int] = []
    for lot in (ui.get("lots") or []):
        if not isinstance(lot, dict):
            continue
        try:
            rid = int(lot.get("id") or 0)
        except Exception:
            rid = 0
        if rid > 0:
            round_lot_ids.append(rid)

    ballots_by_lot = await _fetch_ballots_for_lots(token, round_lot_ids)
    rows = _build_round_result_rows(
        ui,
        results_by_lot=results_by_lot,
        ballots_by_lot=ballots_by_lot,
        round_no=round_no,
    )

    session_out = {
        "id": sess_data.get("id") or session_id,
        "name": sess_data.get("name"),
        "project_name": project_name,
        "project_code": project_code,
        "auction_date": sess_data.get("auction_date"),
        "venue": sess_data.get("venue") or sess_data.get("location"),
        "province": sess_data.get("province"),
    }

    me = await fetch_me(token)
    cc = company_code_from_me(me) or _to_str(sess_data.get("company_code")).strip().lower()
    tpl = resolve_template(cc, DocKind.ROUND_RESULTS)
    for_download = _to_str(download or "").strip().lower() == "html"
    download_html_url = (
        f"/auction/sessions/{session_id}/rounds/{round_no}/results/print?download=html"
    )

    ctx = {
        "request": request,
        "title": title or f"Kết quả vòng {round_no}",
        "session_id": session_id,
        "round_no": round_no,
        "session": session_out,
        "project": {
            "name": project_name or project_code or "",
            "project_code": project_code,
            "auction_mode": auction_mode,
        },
        "price_labels": price_labels,
        "auction_mode": auction_mode,
        "rows": rows,
        "stats": {
            "total_lots": len(rows),
            "won": sum(1 for r in rows if r.get("result_type") == "WINNER"),
            "next": sum(1 for r in rows if r.get("result_type") == "NEXT_ROUND"),
            "pending": sum(1 for r in rows if r.get("result_type") == "PENDING"),
            "no_valid": sum(1 for r in rows if r.get("result_type") == "NO_VALID"),
        },
        "org_name": ORG_NAME,
        "autoprint": 0 if for_download else int(autoprint),
        "for_download": for_download,
        "download_html_url": download_html_url,
        "error": error,
    }

    if for_download:
        html = templates.get_template(tpl).render(**ctx)
        fname = f"ket-qua-vong-{round_no}-phien-{session_id}.html"
        return Response(
            content=html.encode("utf-8"),
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return templates.TemplateResponse(tpl, ctx)
