# routers/dashboard.py
from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from utils.templates import templates           # dùng templates chung (đã có is_logged_in)
from utils.auth import get_access_token, fetch_me  # helpers đọc cookie & gọi /auth/me

router = APIRouter(tags=["Dashboard"])

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # Check đăng nhập thống nhất
    token = get_access_token(request)
    me = await fetch_me(token)
    if not me:
        # chưa login -> chuyển sang trang đăng nhập, giữ next để quay lại /
        return RedirectResponse(url=f"/login?next={quote('/')}", status_code=303)

    # Demo số liệu KPI (như cũ)
    stats = {
        "kpi": {
            "avg_sales": 50897,
            "total_sales": 550897,
            "inquiries": 750897,
            "invoices": 897,
        },
        "lot_status": {
            "available": 25,
            "reserved": 10,
            "sold": 15,
        },
    }

    return templates.TemplateResponse(
        "pages/dashboard/index.html",
        {
            "request": request,
            "title": "Dashboard",
            "breadcrumb": ["Dashboard"],
            "me": me,  # truyền user cho header nếu cần
            "kpi": stats["kpi"],
            "stats": {
                "lot_status_labels": list(stats["lot_status"].keys()),
                "lot_status_values": list(stats["lot_status"].values()),
            },
        },
    )
