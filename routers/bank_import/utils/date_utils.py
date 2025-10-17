from __future__ import annotations
from datetime import datetime

def parse_date(value) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    # Excel serial number?
    try:
        n = float(s)
        base = datetime(1899, 12, 30)
        return base.fromordinal(int(n))  # (đơn giản hoá; đủ tốt cho hầu hết)
    except Exception:
        return None
