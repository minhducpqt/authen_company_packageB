# utils/bid_ticket_issue_client.py
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

from utils.bid_sheet_print import normalize_tickets_for_print
from utils.bid_ticket_qr import qr_png_data_uri

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

# Service A bulk issue giới hạn 500 item/request — chunk để in tới ~10k phiếu.
BULK_ISSUE_CHUNK_SIZE = max(1, min(500, int(os.getenv("BID_TICKET_ISSUE_CHUNK_SIZE", "500"))))
BULK_ISSUE_CHUNK_TIMEOUT = float(os.getenv("BID_TICKET_ISSUE_CHUNK_TIMEOUT", "90"))


def _issue_source_for_print_ctx(print_ctx: Optional[Dict[str, Any]]) -> str:
    if not print_ctx:
        return "PRE_SESSION"
    mode = (print_ctx.get("mode") or "").upper()
    if mode == "TIED_NEXT_ROUND":
        return "TIED"
    if mode.startswith("AUCTION_SESSION"):
        return "SESSION"
    return "PRE_SESSION"


def _company_code_for_issue(
    tickets: List[Dict[str, Any]],
    print_ctx: Optional[Dict[str, Any]],
) -> Optional[str]:
    cc = (print_ctx or {}).get("company_code")
    if cc:
        return str(cc).strip() or None
    for t in tickets:
        cc2 = t.get("company_code")
        if cc2:
            return str(cc2).strip() or None
    return None


def _build_issue_items(
    tickets: List[Dict[str, Any]],
    *,
    src: str,
    print_ctx: Optional[Dict[str, Any]],
    default_session_id: Optional[int],
) -> Tuple[List[Dict[str, Any]], List[int]]:
    """
    Trả (items cho bulk API, chỉ số ticket tương ứng từng item).
    Ticket thiếu project/lot/customer_id bị bỏ qua (giữ hành vi cũ).
    """
    items: List[Dict[str, Any]] = []
    ticket_indices: List[int] = []

    for idx, t in enumerate(tickets):
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
        ticket_indices.append(idx)

    return items, ticket_indices


async def _bulk_issue_one_chunk(
    client: httpx.AsyncClient,
    *,
    headers: Dict[str, str],
    items: List[Dict[str, Any]],
    company_code: Optional[str],
    chunk_no: int,
    chunk_total: int,
) -> List[Dict[str, Any]]:
    params: Dict[str, str] = {}
    if company_code:
        params["company_code"] = company_code

    r = await client.post(
        "/api/v1/bid-tickets/issues/bulk",
        headers=headers,
        params=params or None,
        json={"items": items},
    )
    if r.status_code != 200:
        logger.warning(
            "bid_ticket issue bulk chunk %s/%s failed: HTTP %s body=%s",
            chunk_no,
            chunk_total,
            r.status_code,
            (r.text or "")[:500],
        )
        return []

    js = r.json() or {}
    issued_list = js.get("data") or []
    if len(issued_list) != len(items):
        logger.warning(
            "bid_ticket issue bulk chunk %s/%s size mismatch: sent=%s got=%s",
            chunk_no,
            chunk_total,
            len(items),
            len(issued_list),
        )
    return issued_list


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
    Tự chunk 500 item/lần (giới hạn API A) — hỗ trợ in tới ~10k phiếu.
    """
    if not tickets:
        return tickets

    tickets = normalize_tickets_for_print([dict(t) for t in tickets])

    src = (source or _issue_source_for_print_ctx(print_ctx)).upper()
    items, ticket_indices = _build_issue_items(
        tickets,
        src=src,
        print_ctx=print_ctx,
        default_session_id=default_session_id,
    )

    if not items:
        return tickets

    headers = {"Authorization": f"Bearer {access_token}"}
    company_code = _company_code_for_issue(tickets, print_ctx)

    issued_by_ticket_idx: Dict[int, Dict[str, Any]] = {}
    chunk_total = (len(items) + BULK_ISSUE_CHUNK_SIZE - 1) // BULK_ISSUE_CHUNK_SIZE

    try:
        async with httpx.AsyncClient(
            base_url=SERVICE_A_BASE_URL,
            timeout=BULK_ISSUE_CHUNK_TIMEOUT,
        ) as client:
            for chunk_no, start in enumerate(range(0, len(items), BULK_ISSUE_CHUNK_SIZE), start=1):
                chunk_items = items[start : start + BULK_ISSUE_CHUNK_SIZE]
                chunk_ticket_indices = ticket_indices[start : start + BULK_ISSUE_CHUNK_SIZE]

                try:
                    issued_list = await _bulk_issue_one_chunk(
                        client,
                        headers=headers,
                        items=chunk_items,
                        company_code=company_code,
                        chunk_no=chunk_no,
                        chunk_total=chunk_total,
                    )
                except Exception as exc:
                    logger.exception(
                        "bid_ticket issue bulk chunk %s/%s error: %s",
                        chunk_no,
                        chunk_total,
                        exc,
                    )
                    continue

                for i, ticket_idx in enumerate(chunk_ticket_indices):
                    if i < len(issued_list):
                        issued_by_ticket_idx[ticket_idx] = issued_list[i]
    except Exception as exc:
        logger.exception("bid_ticket issue bulk client error: %s", exc)
        return tickets

    out: List[Dict[str, Any]] = []
    for idx, t in enumerate(tickets):
        t2 = dict(t)
        iss = issued_by_ticket_idx.get(idx)
        if iss:
            token = iss.get("qr_token") or iss.get("jti")
            if token:
                t2["qr_token"] = token
                t2["qr_data_uri"] = qr_png_data_uri(str(token))
        out.append(t2)

    if chunk_total > 1:
        qr_count = sum(1 for x in out if x.get("qr_data_uri"))
        logger.info(
            "bid_ticket QR attach: tickets=%s issued=%s chunks=%s",
            len(tickets),
            qr_count,
            chunk_total,
        )

    return out
