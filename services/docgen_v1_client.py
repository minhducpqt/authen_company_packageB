# services/docgen_v1_client.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


def _headers(token: Optional[str]) -> Dict[str, str]:
    h: Dict[str, str] = {"Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


async def _req(
    method: str,
    path: str,
    token: Optional[str],
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Any:
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=20.0) as client:
        r = await client.request(
            method, path, headers=_headers(token), params=params, json=json_body
        )
    if r.status_code >= 400:
        detail = r.text
        try:
            detail = r.json().get("detail", detail)
        except Exception:
            pass
        raise httpx.HTTPStatusError(
            f"Service A {r.status_code}: {detail}",
            request=r.request,
            response=r,
        )
    if r.status_code == 204:
        return None
    return r.json()


async def list_locality_profiles(token: Optional[str], q: Optional[str] = None) -> List[Dict[str, Any]]:
    params = {"q": q} if q else None
    return await _req("GET", "/api/v1/docgen/locality-profiles", token, params=params)


async def get_locality_profile(token: Optional[str], profile_id: int) -> Dict[str, Any]:
    return await _req("GET", f"/api/v1/docgen/locality-profiles/{profile_id}", token)


async def create_locality_profile(token: Optional[str], body: Dict[str, Any]) -> Dict[str, Any]:
    return await _req("POST", "/api/v1/docgen/locality-profiles", token, json_body=body)


async def update_locality_profile(token: Optional[str], profile_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _req("PUT", f"/api/v1/docgen/locality-profiles/{profile_id}", token, json_body=body)


async def delete_locality_profile(token: Optional[str], profile_id: int) -> None:
    await _req("DELETE", f"/api/v1/docgen/locality-profiles/{profile_id}", token)


async def get_context(token: Optional[str], project_id: int, ward_code: Optional[int] = None) -> Dict[str, Any]:
    params: Dict[str, Any] = {"project_id": project_id}
    if ward_code is not None:
        params["ward_code"] = ward_code
    return await _req("GET", "/api/v1/docgen/context", token, params=params)


async def list_instances(
    token: Optional[str],
    *,
    phase_slug: Optional[str] = None,
    category_slug: Optional[str] = None,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    params = {k: v for k, v in {
        "phase_slug": phase_slug,
        "category_slug": category_slug,
        "project_id": project_id,
        "status": status,
    }.items() if v is not None}
    return await _req("GET", "/api/v1/docgen/instances", token, params=params)


async def get_instance(token: Optional[str], instance_id: int) -> Dict[str, Any]:
    return await _req("GET", f"/api/v1/docgen/instances/{instance_id}", token)


async def create_instance(token: Optional[str], body: Dict[str, Any]) -> Dict[str, Any]:
    return await _req("POST", "/api/v1/docgen/instances", token, json_body=body)


async def update_instance(token: Optional[str], instance_id: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return await _req("PUT", f"/api/v1/docgen/instances/{instance_id}", token, json_body=body)


async def get_render_context(token: Optional[str], instance_id: int) -> Dict[str, Any]:
    return await _req("GET", f"/api/v1/docgen/instances/{instance_id}/render-context", token)


async def finalize_instance(token: Optional[str], instance_id: int) -> Dict[str, Any]:
    return await _req("POST", f"/api/v1/docgen/instances/{instance_id}/finalize", token)


async def fetch_projects(token: Optional[str]) -> List[Dict[str, Any]]:
    data = await _req("GET", "/api/v1/projects", token, params={"page": 1, "size": 200})
    if isinstance(data, list):
        return data
    return data.get("data") or data.get("items") or []


async def fetch_provinces() -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=15.0) as client:
        r = await client.get("/api/v1/_meta/admin-divisions/provinces")
    if r.status_code != 200:
        return []
    return (r.json() or {}).get("items") or []


async def fetch_communes(province_code: int, q: Optional[str] = None) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"province_code": province_code}
    if q:
        params["q"] = q
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=15.0) as client:
        r = await client.get("/api/v1/_meta/admin-divisions/communes", params=params)
    if r.status_code != 200:
        return []
    return (r.json() or {}).get("items") or []
