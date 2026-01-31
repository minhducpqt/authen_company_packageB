# routers/mobile/apis/mobile_auth.py
from __future__ import annotations

import os
from typing import Optional, Any, Dict

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")
AUTH_TIMEOUT = float(os.getenv("AUTH_HTTP_TIMEOUT", "8.0"))

router = APIRouter(prefix="/auth", tags=["mobile-auth"])


# ===== Schemas =====
class LoginPayload(BaseModel):
    username: str
    password: str


class RefreshPayload(BaseModel):
    refresh_token: str


class LogoutPayload(BaseModel):
    refresh_token: Optional[str] = None


# ===== Helpers =====
async def _proxy_json(
    method: str,
    path: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Proxy request to Service A, return JSON or raise HTTPException with upstream error.
    """
    try:
        async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=AUTH_TIMEOUT) as client:
            r = await client.request(method, path, headers=headers, json=json)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Upstream Service A error: {str(e)}")

    if r.status_code >= 400:
        # trả lỗi upstream cho mobile (cố gắng giữ json nếu có)
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise HTTPException(status_code=r.status_code, detail=detail)

    # success
    if r.headers.get("content-type", "").startswith("application/json"):
        return r.json()
    return {"ok": True}


# ===== APIs =====
@router.post("/login")
async def mobile_login(payload: LoginPayload):
    """
    B: POST /api/mobile/auth/login
    -> A: POST /auth/login  (JSON {username,password})
    """
    return await _proxy_json("POST", "/auth/login", json=payload.dict())


@router.post("/refresh")
async def mobile_refresh(payload: RefreshPayload):
    """
    B: POST /api/mobile/auth/refresh
    -> A: POST /auth/refresh
    Lib A nhận refresh token qua cookie / header X-Refresh-Token / body.
    Chọn header cho gọn + đúng design lib.
    """
    headers = {"X-Refresh-Token": payload.refresh_token}
    return await _proxy_json("POST", "/auth/refresh", headers=headers)


@router.get("/me")
async def mobile_me(authorization: Optional[str] = Header(None)):
    """
    B: GET /api/mobile/auth/me
    -> A: GET /auth/me (Bearer)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return await _proxy_json("GET", "/auth/me", headers={"Authorization": authorization})


@router.post("/logout")
async def mobile_logout(
    payload: LogoutPayload,
    authorization: Optional[str] = Header(None),
):
    """
    B: POST /api/mobile/auth/logout
    -> A: POST /auth/logout
    Gửi refresh token qua header X-Refresh-Token (nếu có) + Bearer (nếu có)
    """
    headers: Dict[str, str] = {}
    if authorization:
        headers["Authorization"] = authorization
    if payload.refresh_token:
        headers["X-Refresh-Token"] = payload.refresh_token

    return await _proxy_json("POST", "/auth/logout", headers=headers)


@router.post("/logout_all")
async def mobile_logout_all(authorization: Optional[str] = Header(None)):
    """
    B: POST /api/mobile/auth/logout_all
    -> A: POST /auth/logout_all (Bearer)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return await _proxy_json("POST", "/auth/logout_all", headers={"Authorization": authorization})
