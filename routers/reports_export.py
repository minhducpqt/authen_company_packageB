# routers/reports_export.py
from __future__ import annotations
import os, base64, json
from typing import Optional, Dict, Any

import httpx
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse

from utils.auth import get_access_token

router = APIRouter(prefix="/reports", tags=["Reports"])

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")


# === Helpers ======================================================
def _log(msg: str):
    print(f"[REPORTS_EXPORT] {msg}")

def _b64url_decode(data: str) -> bytes:
    data += "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data.encode("utf-8"))

def _company_from_jwt(token: str | None) -> str | None:
    if not token or token.count(".") != 2:
        return None
    try:
        payload_b = _b64url_decode(token.split(".")[1])
        payload = json.loads(payload_b.decode("utf-8"))
        cc = payload.get("company_code") or payload.get("companyCode")
        return (cc or "").strip() or None
    except Exception:
        return None

def _build_target(kind: str) -> Optional[str]:
    mapping = {
        "lots_eligible":       f"{SERVICE_A_BASE_URL}/api/v1/reports/lot-deposits/eligible",
        "lots_ineligible":     f"{SERVICE_A_BASE_URL}/api/v1/reports/lot-deposits/not-eligible",
        "customers_eligible":  f"{SERVICE_A_BASE_URL}/api/v1/reports/customers/eligible-lots",
        "customers_ineligible":f"{SERVICE_A_BASE_URL}/api/v1/reports/customers/not-eligible-lots",
        "dossier_detail":      f"{SERVICE_A_BASE_URL}/api/v1/reports/dossiers/paid/detail",
        "dossier_summary":     f"{SERVICE_A_BASE_URL}/api/v1/reports/dossiers/paid/summary-customer",
        "dossier_totals_by_type": f"{SERVICE_A_BASE_URL}/api/v1/reports/dossiers/paid/totals-by-type",
    }
    return mapping.get(kind)

def _content_type_for(fmt: str) -> str:
    if fmt.lower() == "xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if fmt.lower() == "csv":
        return "text/csv; charset=utf-8"
    return "application/octet-stream"


# === Main endpoint ================================================
@router.get("/export")
async def export_report(
    request: Request,
    kind: str = Query(..., description="Report kind (lots_eligible, dossier_summary, ...)"),
    project: Optional[str] = Query(None, description="Project code"),
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    fmt: str = Query("xlsx"),
):
    """Proxy xuất báo cáo từ Service A về frontend (XLSX / CSV)."""
    _log(f"BEGIN export_report kind={kind} fmt={fmt} project={project or project_code}")

    # 1️⃣ Token
    token = get_access_token(request)
    if not token:
        _log("⚠️  No token -> redirect to login")
        return RedirectResponse(url=f"/login?next={request.url}", status_code=303)

    company_code = _company_from_jwt(token)
    if not company_code:
        return JSONResponse({"error": "missing_company_code"}, status_code=400)

    # 2️⃣ Xác định endpoint bên A
    target = _build_target(kind)
    if not target:
        return JSONResponse({"error": "unsupported_kind", "kind": kind}, status_code=400)

    # 3️⃣ Chuẩn hóa project
    proj = project or project_code
    if not proj:
        _log("❌ Missing project param → cannot call Service A")
        return JSONResponse({"error": "missing_project_param"}, status_code=422)

    # 4️⃣ Gói params
    params: Dict[str, Any] = {"format": fmt, "project": proj}
    if q: params["q"] = q
    if date_from: params["date_from"] = date_from
    if date_to: params["date_to"] = date_to

    _log(f"→ target={target}")
    _log(f"→ params={params}")

    # 5️⃣ Headers
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Company-Code": company_code,
    }

    # 6️⃣ Call Service A
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.get(target, params=params, headers=headers)
    except Exception as e:
        _log(f"❌ Service A unreachable: {e}")
        return JSONResponse({"error": "service_a_unreachable", "detail": str(e)}, status_code=502)

    # 7️⃣ Handle lỗi
    if resp.status_code != 200:
        try:
            body = resp.json()
        except Exception:
            body = {"detail": resp.text[:300]}
        _log(f"❌ Service A error {resp.status_code}: {body}")
        return JSONResponse(
            {"error": "service_a_failed", "status": resp.status_code, "body": body},
            status_code=resp.status_code,
        )

    # 8️⃣ Stream file về browser
    dispo = resp.headers.get("content-disposition") or f'attachment; filename="{kind}.{fmt}"'
    ctype = resp.headers.get("content-type") or _content_type_for(fmt)
    _log(f"✅ OK → streaming {ctype} ({dispo})")

    return StreamingResponse(
        resp.aiter_bytes(),
        media_type=ctype,
        headers={"Content-Disposition": dispo},
    )
