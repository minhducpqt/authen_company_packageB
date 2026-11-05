from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from utils.project_schedule_warnings import project_schedule_warnings

VN = ZoneInfo("Asia/Ho_Chi_Minh")


def test_missing_all_three_milestones():
    lines = project_schedule_warnings(None, "", None)
    assert len(lines) == 1
    assert "hạn mua hồ sơ" in lines[0]
    assert "hạn nộp tiền đặt trước" in lines[0]
    assert "thời điểm phiên đấu" in lines[0]


def test_deadlines_on_different_vietnam_days():
    lines = project_schedule_warnings(
        "2026-11-02T16:30:00+00:00",  # 23:30 ngày 02/11 tại Việt Nam
        "2026-11-02T17:30:00+00:00",  # 00:30 ngày 03/11 tại Việt Nam
        "2026-11-04T02:00:00+00:00",
    )
    assert any("không cùng một ngày" in line for line in lines)
    assert not any("quá 5 ngày" in line for line in lines)
    assert not any("phải trước" in line for line in lines)


def test_same_day_deadlines_before_auction_within_five_days_are_quiet():
    lines = project_schedule_warnings(
        datetime(2026, 11, 2, 17, 0, tzinfo=VN),
        datetime(2026, 11, 2, 17, 0, tzinfo=VN),
        datetime(2026, 11, 7, 17, 0, tzinfo=VN),
    )
    assert lines == []


def test_auction_exactly_five_days_later_is_quiet_and_one_minute_more_warns():
    start = datetime(2026, 11, 2, 17, 0, tzinfo=VN)
    exact = project_schedule_warnings(start, start, start + timedelta(days=5))
    later = project_schedule_warnings(start, start, start + timedelta(days=5, minutes=1))
    assert exact == []
    assert any("quá 5 ngày" in line for line in later)


def test_deadline_at_or_after_auction_warns():
    auction = datetime(2026, 11, 6, 9, 0, tzinfo=VN)
    same = project_schedule_warnings(auction, auction, auction)
    after = project_schedule_warnings(
        auction + timedelta(hours=1),
        auction - timedelta(days=1),
        auction,
    )
    assert any("phải trước" in line for line in same)
    assert any("Hạn mua hồ sơ" in line and "phải trước" in line for line in after)
    assert not any("quá 5 ngày" in line for line in after)
