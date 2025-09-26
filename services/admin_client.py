# services/admin_client.py
import os
import httpx

SERVICE_A_BASE_URL = os.getenv("SERVICE_A_BASE_URL", "http://127.0.0.1:8800")

def _auth_headers(access: str) -> dict:
    return {"Authorization": f"Bearer {access}"}

class AdminClient:
    def __init__(self, base_url: str = SERVICE_A_BASE_URL):
        self.base_url = base_url

    def get_project_by_code(self, access: str, project_code: str) -> dict:
        with httpx.Client(base_url=self.base_url, timeout=10.0) as c:
            r = c.get(f"/api/v1/projects/by_code/{project_code}", headers=_auth_headers(access))
        j = None
        try:
            j = r.json()
        except Exception:
            pass
        return {"code": r.status_code, "data": j}

    def create_project(self, access: str, payload: dict, *, company_code: str | None = None) -> dict:
        headers = _auth_headers(access)
        if company_code:
            headers["X-Company-Code"] = company_code

        with httpx.Client(base_url=self.base_url, timeout=20.0) as c:
            r = c.post("/api/v1/projects", json=payload, headers=headers)

        j = None
        try:
            j = r.json()
        except Exception:
            pass

        pid = None
        if isinstance(j, dict):
            if isinstance(j.get("id"), int):
                pid = j["id"]
            elif isinstance(j.get("data"), dict) and isinstance(j["data"].get("id"), int):
                pid = j["data"]["id"]
            elif isinstance(j.get("project"), dict) and isinstance(j["project"].get("id"), int):
                pid = j["project"]["id"]

        if pid is None and r.status_code == 200:
            code = (payload or {}).get("project_code")
            if code:
                look = self.get_project_by_code(access, code)
                if isinstance(look.get("data"), dict) and isinstance(look["data"].get("id"), int):
                    pid = look["data"]["id"]
                    j = look["data"]

        return {"code": r.status_code, "id": pid, "data": j}

    def create_lot(self, access: str, project_id: int, payload: dict) -> dict:
        with httpx.Client(base_url=self.base_url, timeout=20.0) as c:
            r = c.post(f"/api/v1/projects/{project_id}/lots", json=payload, headers=_auth_headers(access))
        j = None
        try:
            j = r.json()
        except Exception:
            pass
        return {"code": r.status_code, "data": j}

admin_client = AdminClient()
