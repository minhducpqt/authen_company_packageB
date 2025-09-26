# utils/excel_import.py
from __future__ import annotations
from typing import List, Dict, Tuple, Any
from io import BytesIO
import unicodedata
import os
import httpx

from openpyxl import load_workbook

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")

# =========================
# 1) Chuẩn hoá & validate cơ bản
# =========================

def _strip_accents(s: str) -> str:
    if s is None:
        return ""
    nkfd = unicodedata.normalize("NFD", str(s))
    no_acc = "".join(ch for ch in nkfd if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", no_acc)

def normalize_code(code: str) -> str:
    """
    - Bỏ dấu, upper, bỏ toàn bộ khoảng trắng.
    - Dùng cho: project_code, lot_code.
    """
    if code is None:
        return ""
    code = _strip_accents(code).upper()
    return code.replace(" ", "")

def normalize_text(s: str) -> str:
    """
    - Trim 2 đầu
    - Co cụm whitespace liên tiếp về 1 space
    - Giữ nguyên hoa/thường
    """
    if s is None:
        return ""
    s = str(s).strip()
    parts = s.split()
    return " ".join(parts)

# Các cột bắt buộc trong 2 sheet
REQUIRED_PROJECT_HEADERS = ["project_code", "name"]
REQUIRED_LOT_HEADERS     = ["project_code", "lot_code", "name", "starting_price", "deposit_amount"]

def _headerize(s: str) -> str:
    """
    Chuẩn hoá tên header về snake_case đơn giản.
    Ví dụ: 'Project Code' -> 'project_code'
    """
    s = _strip_accents(str(s)).strip().lower()
    for ch in "-./":
        s = s.replace(ch, " ")
    parts = s.split()
    return "_".join(parts)

async def _get_json(client: httpx.AsyncClient, url: str, headers: Dict[str, str]):
    r = await client.get(url, headers=headers)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, None

# =========================
# 2) Đọc file + chuẩn hoá + kiểm tra mẫu
# =========================

def _read_sheets(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Trả về (projects, lots, errors)
    - Mỗi phần tử là dict đã chuẩn hoá header & dữ liệu cơ bản
    """
    wb = load_workbook(filename=BytesIO(file_bytes), data_only=True)
    names = [ws.title.strip().lower() for ws in wb.worksheets]
    if "projects" not in names or "lots" not in names:
        return [], [], ["Template không hợp lệ. Cần có đủ 2 sheet: 'projects' và 'lots'."]

    ws_p = wb["projects"]
    ws_l = wb["lots"]

    # Headers
    headers_p_raw = list(next(ws_p.iter_rows(min_row=1, max_row=1, values_only=True)))
    headers_l_raw = list(next(ws_l.iter_rows(min_row=1, max_row=1, values_only=True)))

    headers_p = [_headerize(h) for h in headers_p_raw]
    headers_l = [_headerize(h) for h in headers_l_raw]

    errors: List[str] = []
    miss_p = [h for h in REQUIRED_PROJECT_HEADERS if h not in headers_p]
    miss_l = [h for h in REQUIRED_LOT_HEADERS if h not in headers_l]
    if miss_p:
        errors.append(f"Sheet 'projects' thiếu cột bắt buộc: {', '.join(miss_p)}")
    if miss_l:
        errors.append(f"Sheet 'lots' thiếu cột bắt buộc: {', '.join(miss_l)}")
    if errors:
        return [], [], errors

    # Read rows
    projects: List[Dict[str, Any]] = []
    for row in ws_p.iter_rows(min_row=2, values_only=True):
        rec = {headers_p[i]: row[i] for i in range(min(len(headers_p), len(row)))}
        # Chuẩn hoá
        rec["project_code"] = normalize_code(rec.get("project_code", ""))
        rec["name"]         = normalize_text(rec.get("name", ""))
        rec["description"]  = normalize_text(rec.get("description", ""))
        rec["location"]     = normalize_text(rec.get("location", ""))
        projects.append(rec)

    lots: List[Dict[str, Any]] = []
    for row in ws_l.iter_rows(min_row=2, values_only=True):
        rec = {headers_l[i]: row[i] for i in range(min(len(headers_l), len(row)))}
        # Chuẩn hoá
        rec["project_code"]   = normalize_code(rec.get("project_code", ""))
        rec["lot_code"]       = normalize_code(rec.get("lot_code", ""))
        rec["name"]           = normalize_text(rec.get("name", ""))
        rec["description"]    = normalize_text(rec.get("description", ""))
        # số: chấp nhận str số => float, nếu không parse được => None (sẽ bị báo lỗi ở bước validate)
        def _to_float(v):
            if v is None or v == "":
                return None
            try:
                return float(str(v).replace(",", "").replace(" ", ""))
            except Exception:
                return "NaN"
        rec["starting_price"] = _to_float(rec.get("starting_price"))
        rec["deposit_amount"] = _to_float(rec.get("deposit_amount"))
        rec["area"]           = _to_float(rec.get("area"))
        lots.append(rec)

    return projects, lots, []

def _validate_preview(projects: List[Dict[str, Any]], lots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Trả về list lỗi dạng dict {type, row, sheet, field, msg}
    - Kiểm tra thiếu mã/ tên
    - Trùng project_code trong chính file
    - Giá trị số không hợp lệ
    - deposit_amount > starting_price
    - (cơ bản) lot phải có project_code tồn tại trong sheet projects
    """
    errors: List[Dict[str, Any]] = []

    # projects
    seen = set()
    for idx, p in enumerate(projects, start=2):
        if not p.get("project_code"):
            errors.append({"type": "projects", "row": idx, "sheet": "projects", "field": "project_code",
                           "msg": "Thiếu project_code"})
        if not p.get("name"):
            errors.append({"type": "projects", "row": idx, "sheet": "projects", "field": "name",
                           "msg": "Thiếu name"})
        code = p.get("project_code", "")
        if code:
            if code in seen:
                errors.append({"type": "projects", "row": idx, "sheet": "projects", "field": "project_code",
                               "msg": "Trùng project_code trong file"})
            seen.add(code)

    pset = {p.get("project_code") for p in projects if p.get("project_code")}

    # lots
    for idx, l in enumerate(lots, start=2):
        if not l.get("project_code"):
            errors.append({"type": "lots", "row": idx, "sheet": "lots", "field": "project_code",
                           "msg": "Thiếu project_code"})
        if not l.get("lot_code"):
            errors.append({"type": "lots", "row": idx, "sheet": "lots", "field": "lot_code",
                           "msg": "Thiếu lot_code"})
        if not l.get("name"):
            errors.append({"type": "lots", "row": idx, "sheet": "lots", "field": "name",
                           "msg": "Thiếu name"})

        # numeric
        for f in ("starting_price", "deposit_amount"):
            v = l.get(f)
            if v == "NaN":
                errors.append({"type": "lots", "row": idx, "sheet": "lots", "field": f,
                               "msg": "Giá trị không phải số hợp lệ"})
        sp = l.get("starting_price")
        dp = l.get("deposit_amount")
        if isinstance(sp, (int, float)) and isinstance(dp, (int, float)):
            if dp > sp:
                errors.append({"type": "lots", "row": idx, "sheet": "lots", "field": "deposit_amount",
                               "msg": "deposit_amount lớn hơn starting_price"})

        # lot phải reference project_code có trong sheet projects
        if l.get("project_code") and l["project_code"] not in pset:
            errors.append({"type": "lots", "row": idx, "sheet": "lots", "field": "project_code",
                           "msg": "project_code không tồn tại trong sheet projects"})

    return errors

# =========================
# 3) Check tồn tại trên Service A & luật ACTIVE/INACTIVE
# =========================

async def _get_project_by_code(access: str, code: str) -> Dict[str, Any] | None:
    """
    Gọi Service A: GET /api/v1/projects/by_code/{code}
    200 => return json (có status), 404 => None
    """
    headers = {"Authorization": f"Bearer {access}"}
    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=12.0) as client:
        st, data = await _get_json(client, f"/api/v1/projects/by_code/{code}", headers)
        if st == 200 and isinstance(data, dict):
            return data
        return None  # 404 hoặc lỗi coi như không tồn tại

# =========================
# 4) API cho routers/projects.py gọi
# =========================

async def handle_import_preview(file_bytes: bytes, access: str) -> Dict[str, Any]:
    """
    - Đọc, chuẩn hoá, validate template & dữ liệu
    - Kiểm tra tồn tại trên Service A:
        * Nếu dự án đã ACTIVE => không cho cập nhật (push vào errors)
        * Nếu dự án INACTIVE => cho phép cập nhật (đưa vào conflicts_inactive)
    """
    projects, lots, tpl_errs = _read_sheets(file_bytes)
    if tpl_errs:
        # lỗi template → dừng
        return {"ok": False, "errors": [{"msg": e} for e in tpl_errs]}

    data_errs = _validate_preview(projects, lots)
    conflicts_active: List[str] = []
    conflicts_inactive: List[str] = []

    # Check tồn tại trên Service A
    codes = sorted({p["project_code"] for p in projects if p.get("project_code")})
    for code in codes:
        ex = await _get_project_by_code(access, code)
        if ex:
            status = (ex.get("status") or "").upper()
            if status == "ACTIVE":
                # Đã active -> cấm cập nhật
                conflicts_active.append(code)
            else:
                # INACTIVE (hoặc khác) -> cho phép replace
                conflicts_inactive.append(code)

    ok = len(tpl_errs) == 0 and len(data_errs) == 0 and len(conflicts_active) == 0
    return {
        "ok": ok,
        "errors": data_errs,
        "projects": projects,
        "lots": lots,
        "conflicts_active": conflicts_active,     # những mã không được phép cập nhật
        "conflicts_inactive": conflicts_inactive, # những mã có thể replace
    }

from services.admin_client import admin_client  # <- import client mới
def apply_import_projects(payload: Dict[str, Any], access: str, *, company_code: str, force_replace: bool) -> Dict[str, Any]:
    """
    Tạo dự án + lô theo payload preview.
    Trả về:
      - 200: tất cả ok
      - 207: có cái ok, có cái lỗi
      - 400: thất bại
    """
    if not company_code:
        return {"code": 400, "message": "company_code_required"}

    created, replaced, errors = [], [], []
    projects = payload.get("projects") or []
    lots = payload.get("lots") or []

    for p in projects:
        code = (p.get("project_code") or "").strip().upper()

        cp = admin_client.create_project(
            access,
            {
                "project_code": code,
                "name": (p.get("name") or "").strip(),
                "description": p.get("description") or None,
                "location": p.get("location") or None,
                "status": "INACTIVE",
            },
            company_code=company_code,
        )
        if cp.get("code") != 200:
            errors.append({"project_code": code, "stage": "create_project", "message": f"HTTP {cp.get('code')}"})
            continue

        pid = cp.get("id")
        if not pid:
            errors.append({"project_code": code, "stage": "create_project", "message": "missing_id_after_create"})
            continue

        # tạo lots
        for l in [x for x in lots if (x.get("project_code") or "").strip().upper() == code]:
            cl = admin_client.create_lot(
                access,
                pid,
                {
                    "lot_code": l["lot_code"],
                    "name": l.get("name"),
                    "description": l.get("description"),
                    "starting_price": l.get("starting_price"),
                    "deposit_amount": l.get("deposit_amount"),
                    "area": l.get("area"),
                },
            )
            if cl.get("code") != 200:
                errors.append({
                    "project_code": code,
                    "lot_code": l["lot_code"],
                    "stage": "create_lot",
                    "message": f"HTTP {cl.get('code')}",
                })

        replaced.append(code)

    if errors and (created or replaced):
        return {"code": 207, "created": created, "replaced": replaced, "errors": errors}
    if errors and not (created or replaced):
        return {"code": 400, "errors": errors}
    return {"code": 200, "created": created, "replaced": replaced}

# =========================
# 1) PREVIEW
# =========================

async def handle_import_projects(file, access: str) -> Dict[str, Any]:
    """
    Đọc file, validate, chuẩn hóa và xác định các mã trùng/đang active.
    Trả về dict cho trang preview.
    """
    content = await file.read()

    try:
        xls = pd.ExcelFile(io.BytesIO(content))
    except Exception:
        return {"ok": False, "errors": ["File không phải Excel hợp lệ (.xlsx/.xls)."]}

    errors: List[dict] = []
    if not set(["projects", "lots"]).issubset(set(xls.sheet_names)):
        return {"ok": False, "errors": ["Template không hợp lệ. Cần 2 sheet: 'projects' và 'lots'."]}

    dfp = pd.read_excel(xls, sheet_name="projects").fillna("")
    dfl = pd.read_excel(xls, sheet_name="lots").fillna("")

    # validate header
    _ensure_headers(dfp, REQ_PROJECT_COLS, "projects", errors)
    _ensure_headers(dfl, REQ_LOT_COLS, "lots", errors)
    if errors:
        return {"ok": False, "errors": errors}

    # coerce số
    _coerce_numeric(dfl, ["starting_price", "deposit_amount", "area"], "lots", errors)

    # validate rỗng các cột bắt buộc
    if dfp[REQ_PROJECT_COLS].replace("", pd.NA).isnull().any().any():
        errors.append({"sheet": "projects", "msg": "Có ô bắt buộc bị trống (project_code, name)."})
    if dfl[REQ_LOT_COLS].replace("", pd.NA).isnull().any().any():
        errors.append({"sheet": "lots", "msg": "Có ô bắt buộc bị trống ở các cột lots."})
    if errors:
        return {"ok": False, "errors": errors}

    # Chuẩn hóa
    projects: List[Dict[str, Any]] = []
    for r in dfp.to_dict(orient="records"):
        projects.append({
            "project_code": normalize_code(r.get("project_code")),
            "name":          normalize_text(r.get("name")),
            "description":   normalize_text(r.get("description")),
            "location":      normalize_text(r.get("location")),
        })

    lots: List[Dict[str, Any]] = []
    for r in dfl.to_dict(orient="records"):
        lots.append({
            "project_code":  normalize_code(r.get("project_code")),
            "lot_code":      normalize_code(r.get("lot_code")),
            "name":          normalize_text(r.get("name")),
            "description":   normalize_text(r.get("description")),
            "starting_price": float(r["starting_price"]) if f"{r.get('starting_price')}".strip() not in ("", "nan") else None,
            "deposit_amount": float(r["deposit_amount"]) if f"{r.get('deposit_amount')}".strip() not in ("", "nan") else None,
            "area":           float(r["area"]) if f"{r.get('area')}".strip() not in ("", "nan") else None,
        })

    # Validate cơ bản lots: giá cọc <= giá khởi điểm; các cột số phải là số dương (nếu có)
    for idx, l in enumerate(lots, start=2):
        if l["starting_price"] is not None and l["starting_price"] < 0:
            errors.append({"sheet": "lots", "row": idx, "field": "starting_price", "msg": "Phải ≥ 0"})
        if l["deposit_amount"] is not None and l["deposit_amount"] < 0:
            errors.append({"sheet": "lots", "row": idx, "field": "deposit_amount", "msg": "Phải ≥ 0"})
        if (l["starting_price"] is not None and l["deposit_amount"] is not None
                and l["deposit_amount"] > l["starting_price"]):
            errors.append({"sheet": "lots", "row": idx, "field": "deposit_amount", "msg": "Cọc không được lớn hơn giá khởi điểm"})
        if l["area"] is not None and l["area"] <= 0:
            errors.append({"sheet": "lots", "row": idx, "field": "area", "msg": "Phải > 0"})

    # Check trùng / ACTIVE trên server A
    conflicts_active: List[str] = []
    conflicts_inactive: List[str] = []
    seen = set()
    for p in projects:
        code = p["project_code"]
        if not code or code in seen:
            continue
        seen.add(code)
        ex = admin_client.get_project_by_code(access, code)
        if ex.get("code") == 200 and isinstance(ex.get("data"), dict):
            status = (ex["data"].get("status") or "").upper()
            if status == "ACTIVE":
                conflicts_active.append(code)
            else:
                conflicts_inactive.append(code)

    return {
        "ok": True,
        "errors": errors,  # nếu rỗng là OK
        "projects": projects,
        "lots": lots,
        "conflicts_active": conflicts_active,
        "conflicts_inactive": conflicts_inactive,
    }
