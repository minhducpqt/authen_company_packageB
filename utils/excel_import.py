import io
import json
import pandas as pd
from fastapi import UploadFile
from typing import Dict, Any, List
from app.services import admin_client

MANDATORY_PROJECTS = ["project_code", "name"]
MANDATORY_LOTS = ["project_code", "lot_code", "name", "starting_price", "deposit_amount"]

def _ensure_headers(df: pd.DataFrame, required: List[str], sheet_name: str):
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Thiếu cột bắt buộc trong sheet '{sheet_name}': {', '.join(missing)}")

def _coerce_numeric(df: pd.DataFrame, cols: List[str], sheet: str):
    for c in cols:
        if c in df.columns:
            try:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            except Exception:
                raise ValueError(f"Giá trị cột '{c}' ở sheet '{sheet}' không phải số.")

async def handle_import_projects(file: UploadFile, access: str) -> Dict[str, Any]:
    """
    Đọc file, verify template + dữ liệu; trả về preview + danh sách project_code trùng.
    """
    content = await file.read()
    try:
        xls = pd.ExcelFile(io.BytesIO(content))
    except Exception:
        raise ValueError("File tải lên không phải Excel hợp lệ (.xlsx/.xls).")

    if not set(["projects", "lots"]).issubset(set(xls.sheet_names)):
        raise ValueError("Template không hợp lệ. Yêu cầu có đủ 2 sheet: 'projects' và 'lots'.")

    dfp = pd.read_excel(xls, sheet_name="projects").fillna("")
    dfl = pd.read_excel(xls, sheet_name="lots").fillna("")

    _ensure_headers(dfp, MANDATORY_PROJECTS, "projects")
    _ensure_headers(dfl, MANDATORY_LOTS, "lots")

    _coerce_numeric(dfl, ["starting_price", "deposit_amount", "area"], "lots")

    if dfp[MANDATORY_PROJECTS].replace("", pd.NA).isnull().any().any():
        raise ValueError("Sheet 'projects' có dòng thiếu dữ liệu bắt buộc (project_code, name).")
    if dfl[MANDATORY_LOTS].replace("", pd.NA).isnull().any().any():
        raise ValueError("Sheet 'lots' có dòng thiếu dữ liệu bắt buộc (project_code, lot_code, name, starting_price, deposit_amount).")

    # Chuẩn hoá
    projects = []
    for r in dfp.to_dict(orient="records"):
        projects.append({
            "project_code": str(r.get("project_code")).strip(),
            "name": str(r.get("name")).strip(),
            "description": str(r.get("description") or "").strip() or None,
            "location": str(r.get("location") or "").strip() or None,
        })

    lots = []
    for r in dfl.to_dict(orient="records"):
        lots.append({
            "project_code": str(r.get("project_code")).strip(),
            "lot_code": str(r.get("lot_code")).strip(),
            "name": str(r.get("name")).strip(),
            "description": (str(r.get("description")).strip() or None) if "description" in r else None,
            "starting_price": float(r.get("starting_price")) if r.get("starting_price") not in ("", None) else None,
            "deposit_amount": float(r.get("deposit_amount")) if r.get("deposit_amount") not in ("", None) else None,
            "area": float(r.get("area")) if r.get("area") not in ("", None) else None,
        })

    # Xác định trùng mã trên Service A (nếu cần, có thể truyền company_code khi list)
    codes = sorted({p["project_code"] for p in projects})
    conflicts: List[str] = []
    for code in codes:
        ex = admin_client.get_project_by_code(access, code)
        if ex.get("code") == 200 and ex.get("data"):
            conflicts.append(code)

    return {"projects": projects, "lots": lots, "conflicts": conflicts}


def apply_import_projects(payload: Dict[str, Any], access: str, *, company_code: str, force_replace: bool) -> Dict[str, Any]:
    """
    Ghi dữ liệu vào Service A.
    - Project luôn set INACTIVE
    - Lots luôn ACTIVE
    - Nếu trùng project_code -> Server A sẽ REPLACE (đã cài trong API)
    """
    if not company_code:
        return {"code": 400, "message": "company_code_required"}

    created, replaced = [], []
    projects = payload.get("projects") or []
    lots = payload.get("lots") or []

    for p in projects:
        code = p["project_code"]
        name = p["name"]

        cp = admin_client.create_project(
            access,
            {
                "project_code": code,
                "name": name,
                "description": p.get("description"),
                "location": p.get("location"),
                "status": "INACTIVE",
            },
            company_code=company_code,   # <<-- GỬI X-Company-Code
        )
        if cp.get("code") != 200:
            return {
                "code": cp.get("code", 400),
                "message": f"Tạo dự án {code} thất bại: {cp.get('message', 'unknown')}",
            }

        proj = cp.get("data") or {}
        pid = proj.get("id")
        if not pid:
            return {"code": 500, "message": f"Thiếu id sau khi tạo dự án {code}"}

        # Tạo (hoặc replace) lots — Service A set status='ACTIVE'
        for l in [lot for lot in lots if (lot.get("project_code") or "").strip().upper() == code.strip().upper()]:
            cl = admin_client.create_lot(
                access,
                pid,
                {
                    "lot_code": l["lot_code"],
                    "name": l["name"],
                    "description": l.get("description"),
                    "starting_price": l.get("starting_price"),
                    "deposit_amount": l.get("deposit_amount"),
                    "area": l.get("area"),
                },
            )
            if cl.get("code") != 200:
                return {
                    "code": cl.get("code", 400),
                    "message": f"Tạo lô {l['lot_code']} của {code} thất bại: {cl.get('message', 'unknown')}",
                }

        replaced.append(code)  # tạo mới hoặc replace đều coi là replaced cho đơn giản

    return {"code": 200, "created": created, "replaced": replaced}
