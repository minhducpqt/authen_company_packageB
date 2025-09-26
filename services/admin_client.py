# services/admin_client.py
import httpx, os
BASE = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")

def _auth_headers(token: str): return {"Authorization": f"Bearer {token}"}

def get_project_by_code(token: str, code: str):
    with httpx.Client(base_url=BASE, timeout=8.0) as c:
        r = c.get(f"/api/v1/projects/by_code/{code}", headers=_auth_headers(token))
        try: return {"code": r.status_code, "data": r.json()}
        except Exception: return {"code": r.status_code, "data": None}

def create_project(token: str, payload: dict, *, company_code: str):
    headers = _auth_headers(token) | {"X-Company-Code": company_code}
    with httpx.Client(base_url=BASE, timeout=15.0) as c:
        r = c.post("/api/v1/projects", headers=headers, json=payload)
        try: return {"code": r.status_code, "data": r.json()}
        except Exception: return {"code": r.status_code, "data": None}

def create_lot(token: str, project_id: int, payload: dict):
    with httpx.Client(base_url=BASE, timeout=15.0) as c:
        r = c.post(f"/api/v1/projects/{project_id}/lots", headers=_auth_headers(token), json=payload)
        try: return {"code": r.status_code, "data": r.json()}
        except Exception: return {"code": r.status_code, "data": None}
