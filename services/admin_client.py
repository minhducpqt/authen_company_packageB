# utils/services/admin_client.py (WEB) – rút gọn, giả định endpoint đã có
import httpx, os
BASE = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")

def _hdr(acc: str): return {"Authorization": f"Bearer {acc}"}

def get_project_by_code(access: str, code: str):
  url = f"{BASE}/api/v1/admin/projects/by-code/{code}"
  r = httpx.get(url, headers=_hdr(access), timeout=8.0)
  return {"code": r.status_code, "data": r.json() if r.headers.get('content-type','').startswith('application/json') else None}

def create_project(access: str, payload: dict, *, company_code: str):
  url = f"{BASE}/api/v1/admin/projects"
  r = httpx.post(url, headers=_hdr(access) | {"X-Company-Code": company_code}, json=payload, timeout=15.0)
  return {"code": r.status_code, "data": r.json() if r.headers.get('content-type','').startswith('application/json') else None}

def create_lot(access: str, project_id: int, payload: dict):
  url = f"{BASE}/api/v1/admin/projects/{project_id}/lots"
  r = httpx.post(url, headers=_hdr(access), json=payload, timeout=15.0)
  return {"code": r.status_code, "data": r.json() if r.headers.get('content-type','').startswith('application/json') else None}
