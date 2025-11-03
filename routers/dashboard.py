# routers/dashboard.py
from __future__ import annotations
import os
from typing import Any, Dict, List, Tuple, Optional

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

router = APIRouter(tags=["dashboard"])
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


def _log(msg: str):
    print(f"[DASHBOARD_B] {msg}")


async def _get_json(
    path: str,
    token: str,
    params: Optional[Dict[str, Any]] = None,
) -> tuple[int, Any]:
    url = f"{SERVICE_A_BASE_URL}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            r = await c.get(url, headers=headers, params=params or {})
    except Exception as e:
        _log(f"GET {url} EXC: {e}")
        return 599, {"detail": str(e)}
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"detail": r.text[:300]}


@router.get("/", response_class=HTMLResponse)
async def home_redirect():
    # Đưa user về dashboard nếu đã login; nếu chưa login thì middleware/route login sẽ xử lý.
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_index(request: Request):
    """
    Trang dashboard admin — chỉ hiển thị nếu đã đăng nhập.
    Template path: templates/pages/dashboard/index.html
    """
    token = get_access_token(request)
    if not token:
        # chuyển về trang login, quay lại /dashboard sau khi login xong
        return RedirectResponse(url="/login?next=%2Fdashboard", status_code=303)

    # Thử lấy 1 số dữ liệu tổng quan từ Service A (có cũng được, không có thì fallback)
    # Ưu tiên endpoint mới nếu đã tạo; nếu 404 thì để số 0.
    stats = {
        "projects_active": 0,
        "projects_total": 0,
        "customers_total": 0,
        "dossier_orders_total": 0,
        "dossier_amount_vnd": 0,
        "deposit_orders_total": 0,
        "deposit_amount_vnd": 0,
    }

    # 1) Hồ sơ công ty (tên công ty để chào mừng)
    st_cp, data_cp = await _get_json("/api/v1/company/profile", token)
    company_name = ""
    if st_cp == 200 and isinstance(data_cp, dict):
        company_name = (data_cp.get("name") or data_cp.get("company_name") or "").strip()

    # 2) Tổng quan nhanh (endpoint gợi ý; nếu bạn đã triển khai /api/v1/overview/admin/summary)
    st_sm, data_sm = await _get_json("/api/v1/overview/admin/summary", token)
    if st_sm == 200 and isinstance(data_sm, dict):
        for k in stats.keys():
            if k in data_sm and isinstance(data_sm[k], (int, float)):
                stats[k] = data_sm[k]

    # 3) Dự án (đếm nhanh nếu chưa có endpoint summary)
    if stats["projects_total"] == 0:
        st_prj, data_prj = await _get_json("/api/v1/projects?page=1&size=1", token)
        if st_prj == 200 and isinstance(data_prj, dict):
            # nhiều API trả về {items:[], total: N} — lấy total nếu có
            total = data_prj.get("total") or data_prj.get("count")
            if isinstance(total, int):
                stats["projects_total"] = total

    ctx = {
        "request": request,
        "title": "Bảng điều khiển",
        "company_name": company_name,
        "stats": stats,
    }
    return templates.TemplateResponse("pages/dashboard/index.html", ctx)
