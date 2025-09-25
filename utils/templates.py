# utils/templates.py
import os
from starlette.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

# === expose helpers / constants to Jinja ===
ACCESS_COOKIE = os.getenv("ACCESS_COOKIE_NAME", "access_token")

def is_logged_in(request) -> bool:
    # Ưu tiên tên cookie từ .env; fallback 'access_token' nếu khác
    return bool(request.cookies.get(ACCESS_COOKIE) or request.cookies.get("access_token"))

templates.env.globals["ACCESS_COOKIE_NAME"] = ACCESS_COOKIE
templates.env.globals["is_logged_in"] = is_logged_in
