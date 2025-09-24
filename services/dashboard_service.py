def get_dashboard_stats():
    """Hard-code dữ liệu mẫu; sau này thay bằng query DB"""
    return {
        "projects_open": 8,
        "lots_available": 124,
        "new_customers_week": 32,
        "deposit_vnd_today": 450_000_000,
        "revenue_month_vnd": 1_850_000_000,
        "invoices_issued_month": 57,
        "timeseries_deposit": {
            "labels": ["D-6","D-5","D-4","D-3","D-2","Hôm qua","Hôm nay"],
            "amounts": [80,120,150,180,200,390,450]
        },
        "lot_status": {"labels": ["Còn trống","Giữ chỗ","Đã bán"], "values": [124,30,80]},
        "top_projects": {"labels": ["DA-01","DA-02","DA-03"], "amounts": [920,740,680]},
        "funnel": {"labels": ["Mua hồ sơ","Đăng ký","Đặt cọc","Trúng"], "values": [300,180,95,40]},
        "alerts": [
            "5 QR động sắp hết hạn",
            "3 giao dịch chưa đối soát",
            "2 hoá đơn báo lỗi"
        ],
    }
