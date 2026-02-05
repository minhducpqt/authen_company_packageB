# routers/auction_documents_print.py  (Service B - Admin Portal)
from __future__ import annotations

import os
from typing import Any, Dict, Optional, List, Tuple

import httpx
from fastapi import APIRouter, Request, Path, Query
from fastapi.responses import HTMLResponse

from utils.templates import templates
from utils.auth import get_access_token

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


def _aggregate_attendance_from_round_ui(ui: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], int, int]:
    """
    Build attendance aggregated by customer_id from round UI payload (Service A).
    Returns: (attendance_rows_sorted, lot_count, customer_count)
    """
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
        attendance_rows, lot_count, customer_count = _aggregate_attendance_from_round_ui(ui)
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
    }

    project = {"name": project_name or project_code or "", "project_code": project_code or ""}
    stats = {"total_lots": lot_count or 0, "total_customers": customer_count or 0}
    items = _build_print_items(attendance_rows)

    # optional debug payload if you still want
    attendance_payload = {"ok": True, "session": session_out, "data": attendance_rows}

    return templates.TemplateResponse(
        "pages/auction_session_documents/attendance_print.html",
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
#   - Template: pages/auction_session_documents/attendance_public_notice.html
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
        attendance_rows, lot_count, customer_count = _aggregate_attendance_from_round_ui(ui)
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
    }

    project = {"name": project_name or project_code or "", "project_code": project_code or ""}
    stats = {"total_lots": lot_count or 0, "total_customers": customer_count or 0}

    # Keep consistency: provide both rows (for template) and items (optional)
    items = _build_print_items(attendance_rows)

    # raw payload (optional debug)
    attendance_payload = {"ok": True, "session": session_out, "data": attendance_rows}

    return templates.TemplateResponse(
        "pages/auction_session_documents/attendance_public_notice.html",
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
