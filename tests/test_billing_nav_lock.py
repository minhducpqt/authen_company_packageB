from utils.billing_nav_lock import billing_status_nav_locked


def test_running_not_locked():
    assert billing_status_nav_locked({"billing_status": "RUNNING"}) is False


def test_locked_status():
    assert billing_status_nav_locked({"billing_status": "LOCKED"}) is True


def test_lock_until_does_not_lock_menu():
    """lock_until = hạn hiển thị; menu chỉ khóa khi billing_status LOCKED."""
    assert billing_status_nav_locked({"billing_status": "RUNNING", "lock_until": "2099-01-01T00:00:00+00:00"}) is False
