from __future__ import annotations
import os
import typing as t
import datetime as dt
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

class BankClientAsync:
    def __init__(self, base_url: str = SERVICE_A_BASE_URL):
        self.base_url = base_url

    async def get_company_profile(self, access: str) -> tuple[int, dict | None]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=12.0) as c:
            return await _get_json(c, "/api/v1/company/profile", _auth_headers(access))

    async def list_company_bank_accounts(
        self, access: str, *, company_code: str, q: str | None = None,
        status: bool | None = True, page: int = 1, size: int = 200
    ) -> tuple[int, dict | None]:
        params: dict[str, t.Any] = {"company_code": company_code, "page": page, "size": size}
        if q: params["q"] = q
        if status is not None: params["status"] = str(status).lower()
        async with httpx.AsyncClient(base_url=self.base_url, timeout=12.0) as c:
            return await _get_json(c, "/api/v1/company_bank_accounts", _auth_headers(access), params)

    async def list_bank_transactions(
        self, access: str, *, company_code: str,
        account_number: str | None = None,
        bank_code: str | None = None,
        from_date: dt.date | None = None,
        to_date: dt.date | None = None,
        q: str | None = None,
        page: int = 1,
        size: int = 20,
        sort: str = "-txn_time",
        status: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        matched: bool | None = None,          # NEW
        no_ref_only: bool | None = None       # NEW
    ) -> tuple[int, dict | None]:
        params: dict[str, t.Any] = {
            "company_code": company_code, "page": page, "size": size, "sort": sort
        }
        if account_number: params["account_number"] = account_number
        if bank_code: params["bank_code"] = bank_code
        if q: params["q"] = q
        if status: params["status"] = status
        if from_date: params["from_date"] = from_date.isoformat()
        if to_date: params["to_date"] = to_date.isoformat()
        if min_amount is not None: params["min_amount"] = min_amount
        if max_amount is not None: params["max_amount"] = max_amount
        if matched is not None: params["matched"] = str(matched).lower()
        if no_ref_only: params["no_ref_only"] = "true"

        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as c:
            return await _get_json(c, "/api/v1/bank-transactions", _auth_headers(access), params)
