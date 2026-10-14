# utils/templates.py
from starlette.templating import Jinja2Templates
from .auth import get_access_token, fetch_me, account_menu_info  # re-use
import os

templates = Jinja2Templates(directory="templates")

ACCESS_COOKIE_NAME = os.getenv("ACCESS_COOKIE_NAME", "access_token")


def is_logged_in(request) -> bool:
    return bool(get_access_token(request))

templates.env.globals["ACCESS_COOKIE_NAME"] = ACCESS_COOKIE_NAME
templates.env.globals["is_logged_in"] = is_logged_in
templates.env.globals["account_menu_info"] = account_menu_info


def billing_nav_locked(request) -> bool:
    try:
        return bool(getattr(request.state, "billing_nav_locked", False))
    except Exception:
        return False


def billing_lock_detail(request):
    try:
        return getattr(request.state, "billing_lock_detail", None)
    except Exception:
        return None


templates.env.globals["billing_nav_locked"] = billing_nav_locked
templates.env.globals["billing_lock_detail"] = billing_lock_detail

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
