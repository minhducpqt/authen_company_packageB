from __future__ import annotations

from typing import Optional, Any, Dict, List, Tuple

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from routers.mobile.service_a_client import request_json, require_bearer

router = APIRouter(prefix="/customers", tags=["mobile-customers"])


# ===== Schemas (mobile) =====
class CustomerUpsertByCCCDPayload(BaseModel):
    # From QR (trust 100%)
    full_name: str = Field(..., min_length=1)
    cccd: str = Field(..., min_length=6)
    address: Optional[str] = None
    dob: Optional[str] = None  # "YYYY-MM-DD" (date string)

    # Contact (editable)
    phone: str = Field(..., min_length=10, max_length=10)  # bắt buộc 10 số
    email: Optional[str] = None


# ===== Helpers =====
def _norm(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _only_digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


def _validate_phone_10_digits(phone: str) -> str:
    p = _only_digits(phone)
    if len(p) != 10:
        raise HTTPException(status_code=422, detail="phone must be exactly 10 digits")
    return p


# ===== APIs =====
@router.get("")
async def mobile_list_customers(
    authorization: Optional[str] = Header(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1),
    company_code: Optional[str] = Query(None),
):
    """
    B: GET /api/mobile/customers?page=&size=&q=
    -> A: GET /api/v1/customers?page=&size=&q=&company_code=
    Response passthrough: {data,page,size,total}
    """
    bearer = require_bearer(authorization)

    params: List[Tuple[str, Any]] = [("page", page), ("size", size)]
    if q:
        params.append(("q", q))
    if company_code:
        params.append(("company_code", company_code))

    return await request_json(
        "GET",
        "/api/v1/customers",
        headers={"Authorization": bearer},
        params=params,
    )


@router.get("/by-cccd")
async def mobile_check_customer_by_cccd(
    authorization: Optional[str] = Header(None),
    cccd: str = Query(..., min_length=6),
    company_code: Optional[str] = Query(None),
):
    """
    B: GET /api/mobile/customers/by-cccd?cccd=...
    -> A: dùng search list /api/v1/customers?q=<cccd> rồi lọc match CCCD exact (case-insensitive).

    Return:
      { "exists": true, "customer": CustomerOut }
    or
      { "exists": false }
    """
    bearer = require_bearer(authorization)
    cccd_norm = _norm(cccd)

    params: List[Tuple[str, Any]] = [("page", 1), ("size", 20), ("q", cccd)]
    if company_code:
        params.append(("company_code", company_code))

    resp = await request_json(
        "GET",
        "/api/v1/customers",
        headers={"Authorization": bearer},
        params=params,
    )

    rows = (resp or {}).get("data") or []
    found = None
    for r in rows:
        if _norm(r.get("cccd")) == cccd_norm:
            found = r
            break

    if found:
        return {"exists": True, "customer": found}
    return {"exists": False}


@router.post("/upsert-by-cccd")
async def mobile_upsert_customer_by_cccd(
    payload: CustomerUpsertByCCCDPayload,
    authorization: Optional[str] = Header(None),
    company_code: Optional[str] = Query(None),
):
    """
    B: POST /api/mobile/customers/upsert-by-cccd
    -> A:
       - check by CCCD (search list rồi lọc exact)
       - exists => PUT /api/v1/customers/{id}
       - not exists => POST /api/v1/customers

    Payload:
      - CCCD fields (trust): full_name, cccd, address, dob
      - Contact fields: phone (required 10 digits), email (optional)
    """
    bearer = require_bearer(authorization)
    phone = _validate_phone_10_digits(payload.phone)

    # 1) check exists
    check_params: List[Tuple[str, Any]] = [("page", 1), ("size", 20), ("q", payload.cccd)]
    if company_code:
        check_params.append(("company_code", company_code))

    resp = await request_json(
        "GET",
        "/api/v1/customers",
        headers={"Authorization": bearer},
        params=check_params,
    )

    rows = (resp or {}).get("data") or []
    cccd_norm = _norm(payload.cccd)
    existed = None
    for r in rows:
        if _norm(r.get("cccd")) == cccd_norm:
            existed = r
            break

    # 2) build body for A (CustomerCreate/CustomerUpdate compatible)
    body: Dict[str, Any] = {
        "full_name": payload.full_name.strip(),
        "cccd": payload.cccd.strip(),
        "address": (payload.address or "").strip() or None,
        "phone": phone,
        "email": (payload.email or "").strip() or None,
    }
    if payload.dob:
        body["dob"] = payload.dob  # "YYYY-MM-DD"

    # 3) call A
    if existed and existed.get("id"):
        cid = int(existed["id"])
        params: List[Tuple[str, Any]] = []
        if company_code:
            params.append(("company_code", company_code))

        customer = await request_json(
            "PUT",
            f"/api/v1/customers/{cid}",
            headers={"Authorization": bearer},
            params=params,
            json=body,
        )
        return {"ok": True, "action": "updated", "customer": customer}

    # create
    params2: List[Tuple[str, Any]] = []
    if company_code:
        params2.append(("company_code", company_code))

    customer = await request_json(
        "POST",
        "/api/v1/customers",
        headers={"Authorization": bearer},
        params=params2,
        json=body,
    )
    return {"ok": True, "action": "created", "customer": customer}
