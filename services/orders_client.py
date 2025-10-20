# services/orders_client.py
from __future__ import annotations
import os
import typing as t
import httpx

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

def _auth_headers(access: str) -> dict:
    return {"Authorization": f"Bearer {access}"}

async def _get_json(client: httpx.AsyncClient, url: str, headers: dict, params: dict | None = None):
    r = await client.get(url, headers=headers, params=params or {})
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None

class OrdersClientAsync:
    def __init__(self, base_url: str = SERVICE_A_BASE_URL):
        self.base_url = base_url

    async def list_active_projects(self, access: str, *, size: int = 1000) -> tuple[int, t.Any]:
        params = {"status": "ACTIVE", "size": size}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=12.0) as c:
            return await _get_json(c, "/api/v1/projects", _auth_headers(access), params)

    async def list_dossier_orders(
        self,
        access: str,
        *,
        page: int = 1,
        size: int = 100,
        status: str | None = None,
        customer_id: int | None = None,
        project_id: int | None = None,
    ) -> tuple[int, t.Any]:
        params: dict[str, t.Any] = {"page": page, "size": size}
        if status: params["status"] = status
        if customer_id: params["customer_id"] = customer_id
        if project_id: params["project_id"] = project_id

        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as c:
            return await _get_json(c, "/api/v1/dossier-orders", _auth_headers(access), params)

orders_client = OrdersClientAsync()
