from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1.redirect import router as redirect_router
from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.database import engine
from app.exceptions import register_exception_handlers
from app.redis_client import close_redis_pool, get_redis_client
from app.services.rate_limiter import RateLimitMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown resources."""
    yield
    await engine.dispose()
    await close_redis_pool()


app = FastAPI(
    title="URL Shortener",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(RateLimitMiddleware)

register_exception_handlers(app)

app.include_router(v1_router, prefix="/api/v1")


@app.get(
    "/health",
    summary="Health check",
    description="Verify PostgreSQL and Redis connectivity.",
)
async def health_check() -> dict[str, Any]:
    """Return service health status for postgres and redis."""
    postgres_status = "disconnected"
    redis_status = "disconnected"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        postgres_status = "connected"
    except Exception:
        postgres_status = "disconnected"

    try:
        redis = get_redis_client()
        if await redis.ping():
            redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    return {
        "status": "healthy"
        if postgres_status == "connected" and redis_status == "connected"
        else "degraded",
        "postgres": postgres_status,
        "redis": redis_status,
        "version": settings.app_version,
    }


app.include_router(redirect_router)
