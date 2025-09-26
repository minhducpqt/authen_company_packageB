# utils/excel_import.py  (WEB)
from __future__ import annotations
from typing import List, Dict, Any, Tuple
from io import BytesIO
import unicodedata
from openpyxl import load_workbook
from services import admin_client  # dùng client đang gọi Service A

# ---------- Normalize helpers ----------
def _strip_accents(s: str) -> str:
    if s is None: return ""
    nkfd = unicodedata.normalize("NFD", str(s))
    no_acc = "".join(ch for ch in nkfd if not unicodedata.combining(ch))
    return unicodedata.normalize("NFC", no_acc)

def normalize_code(code: str) -> str:
    if code is None: return ""
    return _strip_accents(str(code)).upper().replace(" ", "")

def normalize_text(s: str) -> str:
    if s is None: return ""
    return " ".join(str(s).strip().split())

def _headerize(s: str) -> str:
    s = _strip_accents(str(s)).strip().lower()
    for ch in "-./": s = s.replace(ch, " ")
    return "_".join(s.split())

REQ_PROJECTS = {"project_code", "name"}            # chấp nhận 'project_name'
REQ_LOTS     = {"project_code", "lot_code", "name", "starting_price", "deposit_amount"}

def _validate_headers(headers: List[str], required: set[str], sheet: str) -> List[str]:
    hset = set(headers)
    if "project_name" in hset and "name" not in hset:
        hset.add("name")
    miss = sorted(required - hset)
    return [f"Sheet '{sheet}': thiếu cột bắt buộc: {', '.join(miss)}"] if miss else []

def _read_sheet(ws) -> Tuple[List[str], List[List[Any]]]:
    rows = list(ws.iter_rows(values_only=True))
    if not rows: return [], []
    headers = [_headerize((c or "").strip()) for c in rows[0]]
    return headers, rows[1:]

def _num(v):
    if v in ("", None): return None, None
    try:
        return float(v), None
    except Exception:
        return None, "not_a_number"

# ---------- Preview ----------
async def handle_import_projects(file, access_token: str) -> Dict[str, Any]:
    content = await file.read()
    try:
        wb = load_workbook(BytesIO(content), data_only=True)
    except Exception:
        raise ValueError("File tải lên không phải Excel hợp lệ.")

    sheets = {s.lower(): s for s in wb.sheetnames}
    if "projects" not in sheets or "lots" not in sheets:
        raise ValueError("Template cần đủ 2 sheet: 'projects' và 'lots'.")

    # projects
    ws_p = wb[sheets["projects"]]
    p_headers, p_data = _read_sheet(ws_p)
    errs = _validate_headers(p_headers, REQ_PROJECTS, "projects")
    if errs:
        return {"projects": [], "lots": [], "errors":[{"sheet":"projects","row":1,"field":"_header","msg":errs[0]}], "will_replace":[]}

    p_idx = {h:i for i,h in enumerate(p_headers)}
    projects, errors = [], []

    for ridx, row in enumerate(p_data, start=2):
        code = normalize_code(row[p_idx.get("project_code")] if "project_code" in p_idx else "")
        name = normalize_text(
            row[p_idx.get("name")] if "name" in p_idx else row[p_idx.get("project_name")] if "project_name" in p_idx else ""
        )
        desc = normalize_text(row[p_idx.get("description")]) if "description" in p_idx else ""
        loc  = normalize_text(row[p_idx.get("location")])    if "location" in p_idx else ""

        if not code: errors.append({"sheet":"projects","row":ridx,"field":"project_code","msg":"Thiếu project_code"})
        if not name: errors.append({"sheet":"projects","row":ridx,"field":"name","msg":"Thiếu name"})

        projects.append({"project_code": code, "name": name, "description": desc or None, "location": loc or None})

    # trùng mã trong file
    seen = set()
    for i, p in enumerate(projects, start=2):
        c = p["project_code"]
        if c:
            if c in seen:
                errors.append({"sheet":"projects","row":i,"field":"project_code","msg":"Trùng project_code trong file"})
            seen.add(c)

    # lots
    ws_l = wb[sheets["lots"]]
    l_headers, l_data = _read_sheet(ws_l)
    errs = _validate_headers(l_headers, REQ_LOTS, "lots")
    if errs:
        return {"projects": projects, "lots": [], "errors":[{"sheet":"lots","row":1,"field":"_header","msg":errs[0]}], "will_replace":[]}

    l_idx = {h:i for i,h in enumerate(l_headers)}
    lots = []

    for ridx, row in enumerate(l_data, start=2):
        pj = normalize_code(row[l_idx.get("project_code")])
        lc = normalize_code(row[l_idx.get("lot_code")])
        name = normalize_text(row[l_idx.get("name")])
        desc = normalize_text(row[l_idx.get("description")]) if "description" in l_idx else ""

        sp, e1 = _num(row[l_idx.get("starting_price")])
        dp, e2 = _num(row[l_idx.get("deposit_amount")])
        area, e3 = _num(row[l_idx.get("area")]) if "area" in l_idx else (None, None)

        if not pj:   errors.append({"sheet":"lots","row":ridx,"field":"project_code","msg":"Thiếu project_code"})
        if not lc:   errors.append({"sheet":"lots","row":ridx,"field":"lot_code","msg":"Thiếu lot_code"})
        if not name: errors.append({"sheet":"lots","row":ridx,"field":"name","msg":"Thiếu name"})

        if e1: errors.append({"sheet":"lots","row":ridx,"field":"starting_price","msg":"Giá khởi điểm phải là số"})
        if e2: errors.append({"sheet":"lots","row":ridx,"field":"deposit_amount","msg":"Tiền cọc phải là số"})
        if e3: errors.append({"sheet":"lots","row":ridx,"field":"area","msg":"Diện tích phải là số"})
        if (sp is not None) and (dp is not None) and sp < dp:
            errors.append({"sheet":"lots","row":ridx,"field":"starting_price","msg":"Giá khởi điểm phải ≥ tiền cọc"})

        lots.append({
            "project_code": pj, "lot_code": lc, "name": name, "description": desc or None,
            "starting_price": sp, "deposit_amount": dp, "area": area
        })

    # kiểm tra tồn tại trên Service A: ACTIVE -> lỗi, INACTIVE -> will_replace
    will_replace = []
    codes = sorted({p["project_code"] for p in projects if p["project_code"]})
    for code in codes:
        ex = admin_client.get_project_by_code(access_token, code)
        if ex.get("code") == 200 and ex.get("data"):
            status = (ex["data"].get("status") or "").upper()
            if status == "ACTIVE":
                errors.append({"sheet":"projects","row":"?", "field":"project_code", "msg": f"{code} đang ACTIVE, không thể ghi đè"})
            else:
                will_replace.append(code)

    return {"projects": projects, "lots": lots, "errors": errors, "will_replace": will_replace}

# ---------- Apply ----------
def apply_import_projects(payload: Dict[str, Any], access_token: str, *, company_code: str, force_replace: bool) -> Dict[str, Any]:
    if not company_code:
        return {"code": 400, "message": "company_code_required"}

    projects = payload.get("projects") or []
    lots     = payload.get("lots") or []

    # chặn mọi ACTIVE ở server lần nữa
    for p in projects:
        code = p.get("project_code")
        ex = admin_client.get_project_by_code(access_token, code)
        if ex.get("code") == 200 and ex.get("data"):
            if (ex["data"].get("status") or "").upper() == "ACTIVE":
                return {"code": 409, "message": f"Dự án {code} đang ACTIVE, không thể ghi đè."}

    for p in projects:
        code = p["project_code"]
        cp = admin_client.create_project(
            access_token,
            {"project_code": code, "name": p["name"], "description": p.get("description"), "location": p.get("location"), "status": "INACTIVE"},
            company_code=company_code,
        )
        if cp.get("code") != 200:
            return {"code": cp.get("code", 400), "message": f"Tạo/ghi đè dự án {code} thất bại: {cp.get('message', 'unknown')}"}

        pid = (cp.get("data") or {}).get("id")
        if not pid:
            return {"code": 500, "message": f"Thiếu id sau khi tạo dự án {code}"}

        for l in [x for x in lots if (x.get("project_code") or "").upper() == code.upper()]:
            cl = admin_client.create_lot(access_token, pid, {
                "lot_code": l["lot_code"], "name": l["name"], "description": l.get("description"),
                "starting_price": l.get("starting_price"), "deposit_amount": l.get("deposit_amount"), "area": l.get("area")
            })
            if cl.get("code") != 200:
                return {"code": cl.get("code", 400), "message": f"Tạo lô {l['lot_code']} của {code} thất bại: {cl.get('message','unknown')}"}

    return {"code": 200}
