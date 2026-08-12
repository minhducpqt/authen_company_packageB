# routers/guide.py
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from utils.templates import templates

router = APIRouter(tags=["guide"])


@router.get("/huong-dan", response_class=HTMLResponse)
async def handbook_page(request: Request):
    """Sổ tay hướng dẫn tĩnh — không gọi Service A."""
    return templates.TemplateResponse(
        "pages/guide/handbook.html",
        {"request": request, "title": "Hướng dẫn sử dụng"},
    )


@router.get("/huong-dan/trinh-chieu", response_class=HTMLResponse)
async def present_page(request: Request):
    """Trang trình chiếu giới thiệu chức năng — tĩnh, không gọi Service A."""
    return templates.TemplateResponse(
        "pages/guide/present.html",
        {"request": request, "title": "Giới thiệu chức năng"},
    )
