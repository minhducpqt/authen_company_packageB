# utils/bid_ticket_issue_client.py
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

from utils.bid_sheet_print import normalize_tickets_for_print
from utils.bid_ticket_qr import qr_png_data_uri

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


def _issue_source_for_print_ctx(print_ctx: Optional[Dict[str, Any]]) -> str:
    if not print_ctx:
        return "PRE_SESSION"
    mode = (print_ctx.get("mode") or "").upper()
    if mode == "TIED_NEXT_ROUND":
        return "TIED"
    if mode.startswith("AUCTION_SESSION"):
        return "SESSION"
    return "PRE_SESSION"


async def attach_qr_to_tickets(
    access_token: str,
    tickets: List[Dict[str, Any]],
    *,
    source: Optional[str] = None,
    print_ctx: Optional[Dict[str, Any]] = None,
    default_session_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Gọi Service A bulk issue; gắn qr_token + qr_data_uri vào từng ticket (in-place copy).
    """
    if not tickets:
        return tickets

    tickets = normalize_tickets_for_print([dict(t) for t in tickets])

    src = (source or _issue_source_for_print_ctx(print_ctx)).upper()
    items: List[Dict[str, Any]] = []

    for t in tickets:
        pid = t.get("project_id")
        lid = t.get("lot_id")
        cid = t.get("customer_id")
        if pid is None or lid is None or cid is None:
            continue
        sess = t.get("session_id")
        if sess is None and default_session_id is not None:
            sess = default_session_id
        if sess is None and print_ctx:
            sess = print_ctx.get("session_id")

        items.append(
            {
                "project_id": int(pid),
                "lot_id": int(lid),
                "customer_id": int(cid),
                "session_id": int(sess) if sess is not None else None,
                "round_id": int(t["round_id"]) if t.get("round_id") is not None else None,
                "round_lot_id": int(t["round_lot_id"]) if t.get("round_lot_id") is not None else None,
                "source": src,
            }
        )

    if not items:
        return tickets

    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"items": items}

    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=60.0) as client:
            r = await client.post(
                "/api/v1/bid-tickets/issues/bulk",
                headers=headers,
                json=payload,
            )
        if r.status_code != 200:
            logger.warning(
                "bid_ticket issue bulk failed: HTTP %s body=%s",
                r.status_code,
                (r.text or "")[:500],
            )
            return tickets
        js = r.json() or {}
        issued_list = js.get("data") or []
    except Exception as exc:
        logger.exception("bid_ticket issue bulk error: %s", exc)
        return tickets

    # Map theo thứ tự items đã gửi (API giữ thứ tự)
    issue_idx = 0
    out: List[Dict[str, Any]] = []
    for t in tickets:
        t2 = dict(t)
        pid = t.get("project_id")
        lid = t.get("lot_id")
        cid = t.get("customer_id")
        if pid is None or lid is None or cid is None:
            out.append(t2)
            continue
        if issue_idx < len(issued_list):
            iss = issued_list[issue_idx]
            token = iss.get("qr_token") or iss.get("jti")
            if token:
                t2["qr_token"] = token
                t2["qr_data_uri"] = qr_png_data_uri(str(token))
            issue_idx += 1
        out.append(t2)

    return out
