# routers/reports_export.py
from __future__ import annotations
import os, io, csv, httpx, datetime as dt, urllib.parse
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from utils.auth import get_access_token

router = APIRouter(prefix="/reports", tags=["reports"])
SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8824")

# kind -> (path_on_A, csv_default_field_order)
KIND_MAP: dict[str, tuple[str, List[str]]] = {
    # 5.1 Lô
    "lots_eligible":   ("/api/v1/reports/lot-deposits/eligible",
                        ["company_code","project_code","lot_code","starting_price_vnd","deposit_vnd","total_customers","customer_names","customer_cccds"]),
    "lots_ineligible": ("/api/v1/reports/lot-deposits/not-eligible",
                        ["company_code","project_code","lot_code","reason","total_customers","customer_names","customer_cccds"]),
    # 5.2 Khách hàng
    "customers_eligible":   ("/api/v1/reports/customers/eligible-lots",
                             ["customer_id","full_name","cccd","project_code","eligible_lots","eligible_count"]),
    "customers_ineligible": ("/api/v1/reports/customers/not-eligible-lots",
                             ["customer_id","full_name","cccd","project_code","not_eligible_lots","not_eligible_count","reason"]),
    # 5.3 Mua hồ sơ
    "dossiers_paid_detail":  ("/api/v1/reports/dossiers/paid/detail",
                              ["company_code","project_code","order_code","paid_at","full_name","cccd","dossier_label","qty","unit_price_vnd","line_total_vnd"]),
    "dossiers_paid_summary": ("/api/v1/reports/dossiers/paid/summary-customer",
                              ["customer_id","full_name","cccd","total_qty","total_amount","type_breakdown"]),
    # optional: tổng hợp theo loại
    "dossiers_paid_totals_by_type": ("/api/v1/reports/dossiers/paid/totals-by-type",
                                     ["dossier_label","total_qty","total_amount"]),
}

def _unauth():
    return JSONResponse({"error": "unauthorized"}, status_code=401)

def _filename(kind: str, project: Optional[str], ext: str) -> str:
    pc = (project or "all").replace("/", "-")
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{kind}_{pc}_{ts}.{ext}"

@router.get("/export")
async def export_report(
    request: Request,
    kind: str = Query(..., description="lots_eligible|lots_ineligible|customers_eligible|customers_ineligible|dossiers_paid_detail|dossiers_paid_summary|dossiers_paid_totals_by_type"),
    fmt: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    # Lưu ý: Service A dùng 'project' (không phải project_code). Hỗ trợ cả 2 để tương thích.
    project: Optional[str] = Query(None),
    project_code: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    access = get_access_token(request)
    if not access:
        return _unauth()

    if kind not in KIND_MAP:
        return JSONResponse({"error": "invalid_kind", "supported": list(KIND_MAP)}, status_code=400)

    path_a, csv_order = KIND_MAP[kind]
    params: Dict[str, Any] = {}

    # Chuẩn hoá tham số 'project'
    proj = project or project_code
    if proj:
        params["project"] = proj
    if q: params["q"] = q
    if date_from: params["date_from"] = date_from
    if date_to: params["date_to"] = date_to

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=120.0) as client:
        # --- XLSX: proxy stream từ A ---
        if fmt == "xlsx":
            params["format"] = "xlsx"  # Service A nhận 'format'
            try:
                r = await client.get(path_a, params=params, headers={"Authorization": f"Bearer {access}"})
            except Exception as e:
                return JSONResponse({"error": "service_a_unreachable", "detail": str(e)}, status_code=502)
            if r.status_code != 200:
                # trả lỗi để biết rõ lý do
                body = None
                try:
                    body = r.json()
                except Exception:
                    body = {"detail": r.text[:500]}
                return JSONResponse({"error": "service_a_failed", "status": r.status_code, "body": body}, status_code=502)

            filename = _filename(kind, proj, "xlsx")
            dispo = f'attachment; filename="{urllib.parse.quote(filename)}"'
            return StreamingResponse(
                r.aiter_raw(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": dispo},
            )

        # --- CSV: B gọi A lấy JSON rồi tự kết xuất CSV ---
        try:
            r = await client.get(path_a, params=params, headers={"Authorization": f"Bearer {access}"})
        except Exception as e:
            return JSONResponse({"error": "service_a_unreachable", "detail": str(e)}, status_code=502)

        if r.status_code != 200:
            body = None
            try:
                body = r.json()
            except Exception:
                body = {"detail": r.text[:500]}
            return JSONResponse({"error": "service_a_failed", "status": r.status_code, "body": body}, status_code=502)

        data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
        items: List[Dict[str, Any]] = data.get("items") or data.get("rows") or []

        # Build CSV
        # Ưu tiên field order được định nghĩa; nếu field thiếu/thừa sẽ tự mở rộng
        fieldnames = list(dict.fromkeys([*csv_order, *([k for it in items for k in it.keys()])]))
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for it in items:
            w.writerow(it)
        buf.seek(0)

        filename = _filename(kind, proj, "csv")
        dispo = f'attachment; filename="{urllib.parse.quote(filename)}"'
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": dispo})
