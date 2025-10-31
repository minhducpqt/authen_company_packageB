# routers/reports_export.py
from __future__ import annotations
import os
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse, JSONResponse

from utils.auth import get_access_token

router = APIRouter(prefix="/api/reports/export", tags=["reports-export"])
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


@router.get("/{file_name}")
async def export_xlsx(
    request: Request,
    file_name: str,  # ví dụ: lots_eligible.xlsx, dossiers_paid_detail.xlsx
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: Dict[str, Any] = {}
    if project_code: params["project_code"] = project_code
    if q: params["q"] = q

    # Forward sang Service A
    url = f"/api/v1/reports/exports/{file_name}"
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=None) as c:
        r = await c.get(url, headers={"Authorization": f"Bearer {token}"}, params=params)

    if r.status_code != 200 or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" not in r.headers.get("content-type",""):
        try:
            body = r.json()
        except Exception:
            body = {"detail": r.text[:500]}
        return JSONResponse({"error": "service_a_failed", "status": r.status_code, "body": body}, status_code=502)

    filename = file_name if file_name.endswith(".xlsx") else f"{file_name}.xlsx"
    return StreamingResponse(
        r.aiter_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
