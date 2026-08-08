# utils/project_existing_validate.py
"""
Validate lô của dự án đã tạo — cùng rules ProjectImportVerifier như preview import Excel.
Chỉ chạy trên Service B (đọc lô qua API Service A hiện có).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from utils.project_import_verifier import ProjectImportVerifier


def map_sa_lot_to_verify_input(
    lot: Dict[str, Any],
    *,
    project_code: str,
    row: int,
) -> Dict[str, Any]:
    """Map response list lô Service A → input verifier (giống Excel parse)."""
    return {
        "row": row,
        "project_code": project_code,
        "lot_code": lot.get("lot_code"),
        "name": lot.get("name"),
        "description": lot.get("description"),
        "starting_price": lot.get("starting_price"),
        "deposit_amount": lot.get("deposit_amount"),
        "bid_step_vnd": lot.get("bid_step_vnd"),
        "area": lot.get("area"),
        "lot_id": lot.get("id"),
        "status_lot": lot.get("status"),
    }


def build_existing_project_preview(
    project: Dict[str, Any],
    sa_lots: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Chạy verify trên tất cả lô của 1 dự án đã tồn tại.
    Trả dict cùng shape gần với handle_import_preview (để tái dùng import_preview.html).
    """
    code = (project.get("project_code") or "").strip()
    lots_in: List[Dict[str, Any]] = []
    for i, lot in enumerate(sa_lots or [], start=1):
        if not isinstance(lot, dict):
            continue
        lots_in.append(
            map_sa_lot_to_verify_input(
                lot,
                project_code=code or (lot.get("project_code") or ""),
                row=i,
            )
        )

    verification = ProjectImportVerifier(lots_in).run()

    flat_errors: List[Dict[str, Any]] = []
    for lr in verification.get("lots") or []:
        for e in lr.get("errors") or []:
            flat_errors.append(
                {
                    "type": "lots",
                    "sheet": "lots",
                    "row": lr.get("row"),
                    "field": e.get("field"),
                    "code": e.get("code"),
                    "msg": e.get("message") or e.get("msg"),
                    "lot_code": lr.get("lot_code"),
                    "project_code": lr.get("project_code"),
                }
            )

    has_verify_err = bool(verification.get("has_errors"))
    can_continue = (not has_verify_err) and bool(verification.get("can_continue", True))

    projects = [
        {
            "project_code": code,
            "name": project.get("name"),
            "description": project.get("description"),
            "location": project.get("location"),
        }
    ]

    return {
        "ok": can_continue,
        "template_error": False,
        "mode": "validate_existing",
        "errors": flat_errors,
        "projects": projects,
        "lots": [],  # không apply import
        "lot_preview": verification.get("lots") or [],
        "conflicts_active": [],
        "conflicts_inactive": [],
        "verification": verification,
        "can_continue": can_continue,
        "summary": {
            "totalLots": verification.get("totalLots"),
            "errorCount": verification.get("errorCount") or 0,
            "warningCount": verification.get("warningCount") or 0,
            "totalStartingPrice": verification.get("totalStartingPrice"),
            "totalDeposit": verification.get("totalDeposit"),
            "projectDepositPercent": verification.get("projectDepositPercent"),
            "representativeDepositPercent": verification.get("representativeDepositPercent"),
            "projectWarnings": verification.get("projectWarnings") or [],
        },
        "project_id": project.get("id"),
        "project_code": code,
    }


async def fetch_all_lots_for_project(
    sa_list_lots_fn,
    client,
    *,
    token: str,
    project_code: str,
    page_size: int = 1000,
    max_pages: int = 50,
) -> tuple[int, List[Dict[str, Any]], Optional[str]]:
    """
    Phân trang lấy đủ lô theo project_code.
    Returns: (http_status_last, lots, error_message)
    """
    all_lots: List[Dict[str, Any]] = []
    page = 1
    last_st = 200
    while page <= max_pages:
        st, lst = await sa_list_lots_fn(
            client,
            token=token,
            project_code=project_code,
            size=page_size,
            page=page,
        )
        last_st = st
        if st != 200 or not isinstance(lst, dict):
            return last_st, all_lots, f"Không tải được danh sách lô (HTTP {st})."
        batch = lst.get("data") or []
        if not isinstance(batch, list):
            batch = []
        all_lots.extend([x for x in batch if isinstance(x, dict)])
        total = int(lst.get("total") or 0)
        if len(all_lots) >= total or len(batch) < page_size:
            break
        page += 1
    return last_st, all_lots, None
