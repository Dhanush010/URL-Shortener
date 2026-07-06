from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.shorten import router as shorten_router

router = APIRouter()
router.include_router(shorten_router)
router.include_router(analytics_router)
