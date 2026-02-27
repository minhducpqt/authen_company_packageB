from __future__ import annotations

import os
from typing import Optional, List, Tuple, Any, Dict

import httpx
from fastapi import APIRouter, Request, Query, Path, Body
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from utils.templates import templates
from utils.auth import get_access_token

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8824")

router = APIRouter()


# -----------------------
# Internal HTTP helpers
# -----------------------
async def _api_get(
    client: httpx.AsyncClient,
    path: str,
    token: str,
    params: List[Tuple[str, str | int]] | None = None,
):
    return await client.get(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        timeout=20.0,
    )


async def _api_post_json(
    client: httpx.AsyncClient,
    path: str,
    token: str,
    payload: Any,
    params: List[Tuple[str, str | int]] | None = None,
):
    return await client.post(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        json=payload,
        timeout=25.0,
    )


async def _api_patch_json(
    client: httpx.AsyncClient,
    path: str,
    token: str,
    payload: Any,
    params: List[Tuple[str, str | int]] | None = None,
):
    return await client.patch(
        f"{API_BASE_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or [],
        json=payload,
        timeout=25.0,
    )


def _unauth_redirect(next_path: str) -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={next_path}", status_code=303)


def _map_error(r: httpx.Response) -> JSONResponse:
    if r.status_code == 401:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if r.status_code == 403:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if r.status_code == 404:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if r.status_code >= 500:
        return JSONResponse({"error": "server", "msg": r.text[:300]}, status_code=502)
    try:
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception:
        return JSONResponse({"error": "bad_request", "msg": r.text[:300]}, status_code=r.status_code)


# =========================================================
# BILLING — PAGES
# =========================================================

@router.get("/billing", response_class=HTMLResponse)
async def billing_home_page(request: Request):
    token = get_access_token(request)
    if not token:
        return _unauth_redirect("%2Fbilling")

    return templates.TemplateResponse(
        "pages/billing/index.html",
        {"request": request, "title": "3.3 Billing"},
    )


@router.get("/billing/invoices", response_class=HTMLResponse)
async def billing_invoices_page(
    request: Request,
    from_month: Optional[str] = Query(None, description="YYYY-MM-01"),
    to_month: Optional[str] = Query(None, description="YYYY-MM-01"),
):
    token = get_access_token(request)
    if not token:
        return _unauth_redirect("%2Fbilling%2Finvoices")

    return templates.TemplateResponse(
        "pages/billing/invoices.html",
        {
            "request": request,
            "title": "3.3 Billing — Hóa đơn tháng",
            "init_from_month": from_month or "",
            "init_to_month": to_month or "",
        },
    )


@router.get("/billing/invoices/view/{invoice_id}", response_class=HTMLResponse)
async def billing_invoice_detail_page(
    request: Request,
    invoice_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return _unauth_redirect(f"%2Fbilling%2Finvoices%2Fview%2F{invoice_id}")

    return templates.TemplateResponse(
        "pages/billing/invoice_detail.html",
        {
            "request": request,
            "title": "3.3 Billing — Chi tiết hóa đơn",
            "invoice_id": invoice_id,
        },
    )


# =========================================================
# SUPER BILLING — PAGES (NEW)
# =========================================================

@router.get("/billing/admin/dashboard", response_class=HTMLResponse)
async def billing_admin_dashboard_page(
    request: Request,
    from_month: Optional[str] = Query(None, description="YYYY-MM-01"),
    to_month: Optional[str] = Query(None, description="YYYY-MM-01"),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    """
    Dashboard SUPER:
    - Tổng doanh số VNTECHX theo khoảng tháng
    - breakdown theo công ty
    - có nút chạy cron (gọi run-snapshot)
    """
    token = get_access_token(request)
    if not token:
        return _unauth_redirect("%2Fbilling%2Fadmin%2Fdashboard")

    return templates.TemplateResponse(
        "pages/billing/admin_dashboard.html",
        {
            "request": request,
            "title": "Billing — Dashboard (SUPER)",
            "init_from_month": from_month or "",
            "init_to_month": to_month or "",
            "init_q": q or "",
            "init_page": page,
            "init_size": size,
        },
    )


@router.get("/billing/admin/companies/view/{company_code}", response_class=HTMLResponse)
async def billing_admin_company_detail_page(
    request: Request,
    company_code: str = Path(...),
    from_month: Optional[str] = Query(None, description="YYYY-MM-01"),
    to_month: Optional[str] = Query(None, description="YYYY-MM-01"),
):
    """
    Trang chi tiết 1 công ty (SUPER):
    - status, invoices, payments
    - cấu hình contract (tái sử dụng admin_contracts.html hoặc template riêng)
    """
    token = get_access_token(request)
    if not token:
        return _unauth_redirect(f"%2Fbilling%2Fadmin%2Fcompanies%2Fview%2F{company_code}")

    return templates.TemplateResponse(
        "pages/billing/admin_company_detail.html",
        {
            "request": request,
            "title": f"Billing — Công ty {company_code} (SUPER)",
            "company_code": company_code,
            "init_from_month": from_month or "",
            "init_to_month": to_month or "",
        },
    )


# =========================================================
# A) COMPANY VIEW (token company) — STATUS / INVOICES / PAYMENTS
# (GIỮ NGUYÊN)
# =========================================================

@router.get("/billing/status/data", response_class=JSONResponse)
async def billing_status_data(
    request: Request,
    company_code: Optional[str] = Query(None),  # SUPER only
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = []
    if company_code:
        params.append(("company_code", company_code))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/billing/status", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/invoices/data", response_class=JSONResponse)
async def billing_invoices_data(
    request: Request,
    company_code: Optional[str] = Query(None),  # SUPER only
    from_month: Optional[str] = Query(None),
    to_month: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if company_code:
        params.append(("company_code", company_code))
    if from_month:
        params.append(("from_month", from_month))
    if to_month:
        params.append(("to_month", to_month))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/billing/invoices", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/invoices/{invoice_id}/data", response_class=JSONResponse)
async def billing_invoice_detail_data(
    request: Request,
    invoice_id: int = Path(..., ge=1),
    company_code: Optional[str] = Query(None),  # SUPER only
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = []
    if company_code:
        params.append(("company_code", company_code))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, f"/api/v1/billing/invoices/{invoice_id}", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/invoices/{invoice_id}/projects/data", response_class=JSONResponse)
async def billing_invoice_projects_data(
    request: Request,
    invoice_id: int = Path(..., ge=1),
    company_code: Optional[str] = Query(None),  # SUPER only
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = []
    if company_code:
        params.append(("company_code", company_code))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, f"/api/v1/billing/invoices/{invoice_id}/projects", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/payments/data", response_class=JSONResponse)
async def billing_payments_data(
    request: Request,
    company_code: Optional[str] = Query(None),  # SUPER only
    invoice_id: Optional[int] = Query(None, ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if company_code:
        params.append(("company_code", company_code))
    if invoice_id:
        params.append(("invoice_id", invoice_id))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/billing/payments", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


# =========================================================
# B) SUPER ADMIN — COMPANIES OVERVIEW / CONTRACTS / PAYMENTS / JOBS
# (GIỮ NGUYÊN các route đang hoạt động)
# =========================================================

@router.get("/billing/admin/companies", response_class=HTMLResponse)
async def billing_admin_companies_page(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return _unauth_redirect("%2Fbilling%2Fadmin%2Fcompanies")

    return templates.TemplateResponse(
        "pages/billing/admin_companies.html",
        {
            "request": request,
            "title": "Billing — Tổng quan công ty (SUPER)",
            "init_q": q or "",
            "init_page": page,
            "init_size": size,
        },
    )


@router.get("/billing/admin/companies/data", response_class=JSONResponse)
async def billing_admin_companies_data(
    request: Request,
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if q:
        params.append(("q", q))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/billing/admin/companies", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/admin/contracts", response_class=HTMLResponse)
async def billing_admin_contracts_page(
    request: Request,
    company_code: Optional[str] = Query(None),
    active_only: bool = Query(False),
):
    token = get_access_token(request)
    if not token:
        return _unauth_redirect("%2Fbilling%2Fadmin%2Fcontracts")

    return templates.TemplateResponse(
        "pages/billing/admin_contracts.html",
        {
            "request": request,
            "title": "Billing — Hợp đồng (SUPER)",
            "init_company_code": company_code or "",
            "init_active_only": bool(active_only),
        },
    )


@router.get("/billing/admin/contracts/data", response_class=JSONResponse)
async def billing_admin_contracts_data(
    request: Request,
    company_code: Optional[str] = Query(None),
    active_only: bool = Query(False),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = []
    if company_code:
        params.append(("company_code", company_code))
    if active_only:
        params.append(("active_only", 1))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/billing/contracts", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.post("/billing/admin/contracts/upsert", response_class=JSONResponse)
async def billing_admin_contracts_upsert(
    request: Request,
    payload: Dict[str, Any] = Body(...),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async with httpx.AsyncClient() as client:
        r = await _api_post_json(client, "/api/v1/billing/admin/contracts", token, payload)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.post("/billing/admin/payments/create", response_class=JSONResponse)
async def billing_admin_payment_create(
    request: Request,
    payload: Dict[str, Any] = Body(...),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async with httpx.AsyncClient() as client:
        r = await _api_post_json(client, "/api/v1/billing/admin/payments", token, payload)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.post("/billing/admin/status/patch", response_class=JSONResponse)
async def billing_admin_status_patch(
    request: Request,
    company_code: str = Query(...),
    payload: Dict[str, Any] = Body(...),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("company_code", company_code)]

    async with httpx.AsyncClient() as client:
        r = await _api_patch_json(client, "/api/v1/billing/admin/status", token, payload, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.post("/billing/admin/jobs/run-snapshot", response_class=JSONResponse)
async def billing_admin_run_snapshot(
    request: Request,
    run_date: str = Query(..., description="YYYY-MM-DD"),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("run_date", run_date)]

    async with httpx.AsyncClient() as client:
        r = await _api_post_json(
            client,
            "/api/v1/billing/admin/jobs/run-snapshot",
            token,
            payload={},
            params=params,
        )

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


# =========================================================
# SUPER ADMIN — NEW JSON PROXIES (match Service A additions)
# =========================================================

@router.get("/billing/admin/dashboard/data", response_class=JSONResponse)
async def billing_admin_dashboard_data(
    request: Request,
    from_month: Optional[str] = Query(None, description="YYYY-MM-01"),
    to_month: Optional[str] = Query(None, description="YYYY-MM-01"),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if from_month:
        params.append(("from_month", from_month))
    if to_month:
        params.append(("to_month", to_month))
    if q:
        params.append(("q", q))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, "/api/v1/billing/admin/dashboard", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/admin/companies/{company_code}/status/data", response_class=JSONResponse)
async def billing_admin_company_status_data(
    request: Request,
    company_code: str = Path(...),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, f"/api/v1/billing/admin/companies/{company_code}/status", token, params=[])

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/admin/companies/{company_code}/invoices/data", response_class=JSONResponse)
async def billing_admin_company_invoices_data(
    request: Request,
    company_code: str = Path(...),
    from_month: Optional[str] = Query(None),
    to_month: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if from_month:
        params.append(("from_month", from_month))
    if to_month:
        params.append(("to_month", to_month))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, f"/api/v1/billing/admin/companies/{company_code}/invoices", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/admin/companies/{company_code}/invoices/{invoice_id}/data", response_class=JSONResponse)
async def billing_admin_company_invoice_detail_data(
    request: Request,
    company_code: str = Path(...),
    invoice_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async with httpx.AsyncClient() as client:
        r = await _api_get(
            client,
            f"/api/v1/billing/admin/companies/{company_code}/invoices/{invoice_id}",
            token,
            params=[],
        )

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/admin/companies/{company_code}/invoices/{invoice_id}/projects/data", response_class=JSONResponse)
async def billing_admin_company_invoice_projects_data(
    request: Request,
    company_code: str = Path(...),
    invoice_id: int = Path(..., ge=1),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    async with httpx.AsyncClient() as client:
        r = await _api_get(
            client,
            f"/api/v1/billing/admin/companies/{company_code}/invoices/{invoice_id}/projects",
            token,
            params=[],
        )

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)


@router.get("/billing/admin/companies/{company_code}/payments/data", response_class=JSONResponse)
async def billing_admin_company_payments_data(
    request: Request,
    company_code: str = Path(...),
    invoice_id: Optional[int] = Query(None, ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    token = get_access_token(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    params: List[Tuple[str, str | int]] = [("page", page), ("size", size)]
    if invoice_id:
        params.append(("invoice_id", invoice_id))

    async with httpx.AsyncClient() as client:
        r = await _api_get(client, f"/api/v1/billing/admin/companies/{company_code}/payments", token, params)

    if r.status_code != 200:
        return _map_error(r)
    return JSONResponse(r.json(), status_code=200)