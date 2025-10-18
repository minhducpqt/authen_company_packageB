# utils/templates.py
from starlette.templating import Jinja2Templates
from .auth import get_access_token, fetch_me  # re-use
import os

templates = Jinja2Templates(directory="templates")

ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")

def is_logged_in(request) -> bool:
    return bool(get_access_token(request))

templates.env.globals["ACCESS_COOKIE_NAME"] = ACCESS_COOKIE_NAME
templates.env.globals["is_logged_in"] = is_logged_in

from datetime import datetime

def datetimeformat(value, fmt="%d/%m/%Y %H:%M:%S"):
    if not value:
        return ""
    try:
        if isinstance(value, datetime):
            return value.strftime(fmt)
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime(fmt)
    except Exception:
        return str(value)

templates.env.filters["datetimeformat"] = datetimeformat
