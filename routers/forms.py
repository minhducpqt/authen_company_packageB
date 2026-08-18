# routers/forms.py — Entry: gộp hub biểu mẫu + studio preview (add-on)
from __future__ import annotations

from fastapi import APIRouter

from routers.docgen_auction_minutes import router as auction_minutes_router
from routers.docgen_v1 import router as docgen_router
from routers.forms_bid_sheet import router as bid_sheet_router
from routers.forms_hub import router as hub_router

router = APIRouter(tags=["forms"])
router.include_router(docgen_router, prefix="/bieu-mau")
router.include_router(auction_minutes_router, prefix="/bieu-mau")
router.include_router(hub_router, prefix="/bieu-mau")
router.include_router(bid_sheet_router, prefix="/bieu-mau")
