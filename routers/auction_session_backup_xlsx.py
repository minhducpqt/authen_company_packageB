# routers/auction_session_backup_xlsx.py
"""Proxy the per-lot session backup workbook. Does not write auction data."""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse, Response

from utils.auth import get_access_token

router = APIRouter(tags=["auction_session_backup_xlsx"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/auction/sessions/{session_id}/backup-xlsx")
async def download_session_backup_xlsx(
    request: Request,
    session_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    role = (request.cookies.get("user_role") or "").strip().upper()
    if role != "SUPER_ADMIN":
        return JSONResponse({"detail": "Forbidden"}, status_code=403)

    url = f"{SERVICE_A_BASE_URL}/api/v1/auction-sessions/sessions/{int(session_id)}/backup-xlsx"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            upstream = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    except Exception as exc:
        return JSONResponse({"detail": str(exc)}, status_code=502)
    if upstream.status_code != 200:
        try:
            body = upstream.json()
        except Exception:
            body = {"detail": (upstream.text or "")[:300]}
        return JSONResponse(body, status_code=upstream.status_code)
    disposition = upstream.headers.get("content-disposition") or "attachment"
    return Response(
        content=upstream.content,
        media_type=_XLSX,
        headers={"Content-Disposition": disposition},
    )
