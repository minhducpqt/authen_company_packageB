"""UI-only billing nav lock when billing.company_status is LOCKED."""
from __future__ import annotations

from typing import Any, Dict, Optional


def billing_status_nav_locked(status: Optional[Dict[str, Any]]) -> bool:
    """True only when billing_status is LOCKED (lock_until = hạn/thông tin hiển thị, không dùng để khóa menu)."""
    if not status or not isinstance(status, dict):
        return False
    return str(status.get("billing_status") or "RUNNING").upper() == "LOCKED"
