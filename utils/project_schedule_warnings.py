"""Cảnh báo mốc thời gian trên danh sách dự án. Không đổi dữ liệu dự án."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_FIVE_DAYS = timedelta(days=5)


def _parse_vn(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        text = str(raw).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_VN_TZ)
    else:
        dt = dt.astimezone(_VN_TZ)
    return dt


def _join(parts: List[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} và {parts[1]}"
    return ", ".join(parts[:-1]) + " và " + parts[-1]


def project_schedule_warnings(
    application_deadline_at: Any,
    deposit_deadline_at: Any,
    auction_at: Any,
) -> List[str]:
    """Ba mốc phải có, hai hạn cùng ngày, và phiên đấu sau hạn không quá 5 ngày."""
    application = _parse_vn(application_deadline_at)
    deposit = _parse_vn(deposit_deadline_at)
    auction = _parse_vn(auction_at)
    warnings: List[str] = []

    missing: List[str] = []
    if application is None:
        missing.append("hạn mua hồ sơ")
    if deposit is None:
        missing.append("hạn nộp tiền đặt trước")
    if auction is None:
        missing.append("thời điểm phiên đấu")
    if missing:
        warnings.append(f"Chưa thiết lập {_join(missing)}.")

    if application is not None and deposit is not None:
        if application.date() != deposit.date():
            warnings.append("Hạn mua hồ sơ và hạn nộp tiền đặt trước không cùng một ngày.")

    deadlines = [item for item in (application, deposit) if item is not None]
    if auction is not None and deadlines:
        late: List[str] = []
        if application is not None and application >= auction:
            late.append("Hạn mua hồ sơ")
        if deposit is not None and deposit >= auction:
            late.append("Hạn nộp tiền đặt trước")
        if late:
            warnings.append(f"{_join(late)} phải trước thời điểm phiên đấu.")

        anchor = max(deadlines)
        if auction > anchor and auction - anchor > _FIVE_DAYS:
            if application is not None and deposit is not None:
                gap = "hạn mua hồ sơ và hạn nộp tiền đặt trước"
            elif application is not None:
                gap = "hạn mua hồ sơ"
            else:
                gap = "hạn nộp tiền đặt trước"
            warnings.append(f"Phiên đấu diễn ra sau {gap} quá 5 ngày.")
    return warnings
