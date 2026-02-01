# routers/mobile/apis/mobile_auth.py
from __future__ import annotations

from typing import Optional, Dict

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from routers.mobile.service_a_client import request_json

router = APIRouter(prefix="/auth", tags=["mobile-auth"])


# ===== Schemas =====
class LoginPayload(BaseModel):
    username: str
    password: str


class RefreshPayload(BaseModel):
    refresh_token: str


class LogoutPayload(BaseModel):
    refresh_token: Optional[str] = None


# ===== APIs =====
@router.post("/login")
async def mobile_login(payload: LoginPayload):
    """
    B: POST /api/mobile/auth/login
    -> A: POST /auth/login  (JSON {username,password})
    """
    return await request_json("POST", "/auth/login", json=payload.dict())


@router.post("/refresh")
async def mobile_refresh(payload: RefreshPayload):
    """
    B: POST /api/mobile/auth/refresh
    -> A: POST /auth/refresh
    Lib A nhận refresh token qua cookie / header X-Refresh-Token / body.
    Chọn header cho gọn + đúng design lib.
    """
    headers = {"X-Refresh-Token": payload.refresh_token}
    return await request_json("POST", "/auth/refresh", headers=headers)


@router.get("/me")
async def mobile_me(authorization: Optional[str] = Header(None)):
    """
    B: GET /api/mobile/auth/me
    -> A: GET /auth/me (Bearer)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return await request_json("GET", "/auth/me", headers={"Authorization": authorization})


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

    return await request_json("POST", "/auth/logout", headers=headers)


@router.post("/logout_all")
async def mobile_logout_all(authorization: Optional[str] = Header(None)):
    """
    B: POST /api/mobile/auth/logout_all
    -> A: POST /auth/logout_all (Bearer)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return await request_json("POST", "/auth/logout_all", headers={"Authorization": authorization})
