from fastapi import APIRouter

from app.api.v1.shorten import router as shorten_router

router = APIRouter()
router.include_router(shorten_router)
