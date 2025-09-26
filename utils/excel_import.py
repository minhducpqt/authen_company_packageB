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

async def apply_import_projects(payload: Dict[str, Any], access: str, *, company_code: str) -> Dict[str, Any]:
    """
    Ghi dữ liệu lên Service A (từng dự án một).
    - Yêu cầu: những mã có trong conflicts_active bị reject từ trước (preview).
    - Project tạo/replace: POST /api/v1/projects  (X-Company-Code)
    - Lots tạo theo: POST /api/v1/projects/{project_id}/lots
    """
    if not company_code:
        return {"code": 400, "message": "company_code_required"}

    headers = {"Authorization": f"Bearer {access}", "X-Company-Code": company_code}
    projects = payload.get("projects") or []
    lots     = payload.get("lots") or []
    conflicts_active = set(payload.get("conflicts_active") or [])

    created, replaced, errors = [], [], []

    async with httpx.AsyncClient(base_url=SERVICE_A_BASE_URL, timeout=30.0) as client:
        for p in projects:
            code = p.get("project_code")
            name = p.get("name")
            if not code or not name:
                errors.append(f"Bỏ qua dự án thiếu code/name (code={code})")
                continue

            if code in conflicts_active:
                errors.append(f"Dự án {code} đang ACTIVE, không ghi đè.")
                continue

            # Tạo/replace project (server A chịu trách nhiệm interpret replace)
            resp = await client.post(
                "/api/v1/projects",
                headers=headers,
                json={
                    "project_code": code,
                    "name": name,
                    "description": p.get("description") or None,
                    "location": p.get("location") or None,
                    "status": "INACTIVE",  # mặc định
                },
            )
            try:
                data = resp.json()
            except Exception:
                data = None

            if resp.status_code != 200 or not isinstance(data, dict):
                errors.append(f"Tạo/cập nhật dự án {code} thất bại (HTTP {resp.status_code}).")
                continue

            proj = data.get("data") or data  # tuỳ API trả {data:{...}} hay {...}
            pid = proj.get("id")
            if not pid:
                errors.append(f"Dự án {code}: không nhận được id sau khi tạo.")
                continue

            # Lots thuộc dự án code
            related_lots = [l for l in lots if (l.get("project_code") or "") == code]
            for l in related_lots:
                body = {
                    "lot_code": l.get("lot_code"),
                    "name": l.get("name"),
                    "description": l.get("description") or None,
                    "starting_price": l.get("starting_price"),
                    "deposit_amount": l.get("deposit_amount"),
                    "area": l.get("area"),
                }
                resp2 = await client.post(
                    f"/api/v1/projects/{pid}/lots",
                    headers={"Authorization": f"Bearer {access}"},
                    json=body,
                )
                if resp2.status_code != 200:
                    errors.append(f"Tạo lô {l.get('lot_code')} của dự án {code} thất bại (HTTP {resp2.status_code}).")

            replaced.append(code)  # coi như replace cho đơn giản

    code = 200 if not errors else 207  # 207 = multi-status
    return {"code": code, "created": created, "replaced": replaced, "errors": errors}
