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
  """
  Trang root của Service B: luôn đưa user về Dashboard mới (/reports).
  Login xong nếu redirect về "/" thì sẽ tự sang /reports.
  """
  return RedirectResponse(url="/reports", status_code=303)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_index(request: Request):
  """
  Giữ route /dashboard để tương thích ngược, nhưng chuyển hướng sang /reports.
  Login cũ đang dùng next=/dashboard vẫn hoạt động, chỉ là bị chuyển sang /reports.
  """
  return RedirectResponse(url="/reports", status_code=303)
