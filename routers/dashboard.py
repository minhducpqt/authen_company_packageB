# routers/dashboard.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

templates = Jinja2Templates(directory="templates")

router = APIRouter(tags=["Dashboard"])

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
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
            "kpi": stats["kpi"],
            "stats": {
                "lot_status_labels": list(stats["lot_status"].keys()),
                "lot_status_values": list(stats["lot_status"].values()),
            },
        },
    )
