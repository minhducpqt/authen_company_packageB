# services/auction_minutes_context.py — Dữ liệu biên bản đấu giá TP-ĐGTS-18
from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

from services.docgen_v1_client import list_instances

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824").rstrip("/")


async def _a_get(
    path: str,
    token: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 60.0,
) -> Tuple[int, Any]:
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            r = await client.get(url, headers=headers, params=params or {})
        except Exception as e:
            return 599, {"detail": str(e)}
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"detail": (r.text or "")[:800]}


def _data_list(js: Any) -> List[Dict[str, Any]]:
    if not isinstance(js, dict):
        return []
    data = js.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def _data_obj(js: Any) -> Dict[str, Any]:
    if not isinstance(js, dict):
        return {}
    data = js.get("data")
    if isinstance(data, dict):
        return data
    return js if js.get("id") is not None else {}


def _fmt_date_vn(raw: Any) -> str:
    s = str(raw or "").strip()
    if len(s) >= 10 and "-" in s:
        return f"{s[8:10]}/{s[5:7]}/{s[0:4]}"
    return s


def _fmt_vnd_dot(v: Any) -> str:
    if v is None or v == "":
        return ""
    try:
        n = int(float(v))
    except Exception:
        return str(v)
    neg = n < 0
    s = f"{abs(n):,}".replace(",", ".")
    return f"-{s}" if neg else s


def _progression_narrative(round_sections: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for sec in round_sections or []:
        rn = sec.get("round_no") or "?"
        stats = sec.get("stats") or {}
        lines.append(
            f"Vòng {rn}: {stats.get('total_lots', 0)} lô — "
            f"trúng {stats.get('won', 0)}, vào vòng trong {stats.get('next', 0)}, "
            f"không thành {stats.get('no_valid', 0)}, chưa chốt {stats.get('pending', 0)}."
        )
        for row in sec.get("rows") or []:
            lot = row.get("lot_code") or "—"
            st = row.get("status_short") or row.get("status_label") or ""
            detail = row.get("detail") or ""
            if detail:
                first = (detail.split("\n") or [""])[0]
                lines.append(f"  • Lô {lot} ({st}): {first}")
            else:
                lines.append(f"  • Lô {lot}: {st}")
    return "\n".join(lines) if lines else ""


async def fetch_auction_minutes_context(
    token: str,
    *,
    session_id: int,
    project_id: Optional[int] = None,
    company_name: str = "",
    fields_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Tổng hợp dữ liệu in biên bản đấu giá theo phiên."""
    from routers.auction_documents_print import (
        _build_session_failed_lots,
        _build_session_won_lots,
        _fetch_ballots_for_lots,
        _fetch_round_rows_for_print,
        _price_column_labels,
        _r1_start_prices_map,
        _r1_ui_lots_by_id,
        _normalize_auction_mode,
    )

    error: Optional[str] = None
    st_s, sess_js = await _a_get(f"/api/v1/auction-sessions/sessions/{session_id}", token)
    sess = _data_obj(sess_js) if st_s == 200 else {}
    if st_s != 200:
        error = f"Không tải được phiên (status={st_s})"

    pid = project_id or sess.get("project_id")
    try:
        pid = int(pid) if pid else None
    except Exception:
        pid = None

    project_name = sess.get("project_name") or sess.get("p_project_name") or ""
    project_code = sess.get("project_code") or sess.get("p_project_code") or ""
    auction_mode = "PER_LOT"

    if pid:
        st_p, prj_js = await _a_get(f"/api/v1/projects/{pid}", token)
        if st_p == 200:
            pdata = _data_obj(prj_js)
            project_name = pdata.get("name") or project_name
            project_code = pdata.get("project_code") or project_code
            if pdata.get("auction_mode"):
                auction_mode = _normalize_auction_mode(pdata.get("auction_mode"))

    st_res, res_js = await _a_get(f"/api/v1/auction-sessions/sessions/{session_id}/results", token)
    session_results = _data_list(res_js) if st_res == 200 else []
    results_by_lot: Dict[int, Dict[str, Any]] = {}
    for row in session_results:
        try:
            lid = int(row.get("lot_id") or 0)
        except Exception:
            continue
        if lid > 0:
            results_by_lot[lid] = row

    st_rnd, rnd_js = await _a_get(f"/api/v1/auction-sessions/sessions/{session_id}/rounds", token)
    round_nos = sorted(
        {
            int(r.get("round_no") or 0)
            for r in _data_list(rnd_js)
            if int(r.get("round_no") or 0) > 0
        }
    )
    if not round_nos:
        round_nos = [1]

    st_ui1, ui_r1_js = await _a_get(
        f"/api/v1/auction-sessions/sessions/{session_id}/rounds/1/ui", token
    )
    ui_r1 = ui_r1_js if isinstance(ui_r1_js, dict) and st_ui1 == 200 else {}
    r1_prices = _r1_start_prices_map(ui_r1, auction_mode=auction_mode)
    r1_ui_lots = _r1_ui_lots_by_id(ui_r1)
    r1_ids: List[int] = []
    for lot in ui_r1.get("lots") or []:
        try:
            rid = int(lot.get("id") or 0)
        except Exception:
            rid = 0
        if rid > 0:
            r1_ids.append(rid)
    r1_ballots = await _fetch_ballots_for_lots(token, r1_ids)

    ineligible_rows: List[Dict[str, Any]] = []
    if pid:
        try:
            from routers.auction_documents_print import _fetch_project_lots_ineligible

            ineligible_rows = await _fetch_project_lots_ineligible(token, pid)
        except Exception:
            ineligible_rows = []

    failed_lots_pre, failed_lots_in = _build_session_failed_lots(
        session_results,
        ui_r1=ui_r1,
        r1_prices=r1_prices,
        r1_ballots=r1_ballots,
        r1_ui_lots_by_id=r1_ui_lots,
        ineligible_rows=ineligible_rows,
        auction_mode=auction_mode,
    )
    failed_lots = failed_lots_pre + failed_lots_in
    won_lots = _build_session_won_lots(
        session_results,
        r1_prices=r1_prices,
        r1_ui_lots_by_id=r1_ui_lots,
        auction_mode=auction_mode,
    )

    round_pairs = await asyncio.gather(
        *[
            _fetch_round_rows_for_print(token, session_id, rn, results_by_lot=results_by_lot)
            for rn in round_nos
        ]
    )
    round_sections = [
        {"round_no": rn, "rows": rows, "stats": stats}
        for rn, rows, stats in sorted(round_pairs, key=lambda x: x[0])
    ]

    contract_no = ""
    contract_date = ""
    party_a = company_name or ""
    party_b = ""
    asset_title = project_name or project_code or sess.get("name") or ""

    if pid:
        try:
            inst_data = await list_instances(
                token,
                project_id=pid,
                phase_slug="truoc-phien",
                category_slug="hop-dong",
            )
            for inst in inst_data.get("items") or []:
                if inst.get("status") != "FINAL":
                    continue
                fields = inst.get("fields") or {}
                contract = fields.get("contract") or {}
                contract_no = str(contract.get("document_no") or inst.get("document_no") or "").strip()
                contract_date = _fmt_date_vn(contract.get("signed_at") or "")
                party_a = str(fields.get("party_a_name") or party_a).strip()
                party_b = str(fields.get("party_b_name") or "").strip()
                asset_title = str(contract.get("subtitle") or asset_title).strip()
                break
        except Exception:
            pass

    venue = sess.get("venue") or sess.get("location") or ""
    auction_date = _fmt_date_vn(sess.get("auction_date") or "")

    default_fields: Dict[str, Any] = {
        "form_code": "TP-ĐGTS-18",
        "contract_no": contract_no,
        "contract_date": contract_date,
        "party_a": party_a,
        "party_b": party_b,
        "session_time_h": "",
        "session_time_m": "",
        "session_date": auction_date,
        "venue": venue,
        "organizer": company_name or party_a,
        "asset_description": asset_title,
        "starting_price_note": "Xem danh sách lô và giá khởi điểm kèm theo / bảng kết quả vòng 1.",
        "guests": ["", ""],
        "asset_owner": "",
        "auctioneer": "",
        "bidders_note": "Danh sách người tham gia đấu giá theo sổ điểm danh phiên.",
        "progression_text": _progression_narrative(round_sections),
        "end_time_h": "",
        "end_time_m": "",
        "end_date": auction_date,
    }

    if fields_override:
        for k, v in fields_override.items():
            if v is not None:
                default_fields[k] = v

    return {
        "error": error,
        "session_id": session_id,
        "project_id": pid,
        "session": sess,
        "project": {"name": project_name, "project_code": project_code},
        "auction_mode": auction_mode,
        "price_labels": _price_column_labels(auction_mode),
        "fields": default_fields,
        "failed_lots": failed_lots,
        "failed_lots_pre_session": failed_lots_pre,
        "failed_lots_in_session": failed_lots_in,
        "won_lots": won_lots,
        "round_sections": round_sections,
        "company_name": company_name,
    }
