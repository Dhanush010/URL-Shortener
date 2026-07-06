import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import get_settings
from app.exceptions import rate_limit_exceeded_response
from app.redis_client import get_redis_client

RATE_LIMIT_KEY_PREFIX = "ratelimit:"


def get_client_ip(request: Request) -> str:
    """Extract the client IP, honoring X-Forwarded-For when present."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


async def check_rate_limit(client_ip: str) -> tuple[bool, int]:
    """
    Apply sliding-window rate limiting for the given client IP.

    Returns:
        A tuple of (allowed, retry_after_seconds). retry_after is 0 when allowed.
    """
    settings = get_settings()
    redis = get_redis_client()
    now = int(time.time())
    window = now // settings.rate_limit_window_seconds
    key = f"{RATE_LIMIT_KEY_PREFIX}{client_ip}:{window}"

    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.rate_limit_window_seconds * 2)

    if count > settings.rate_limit_requests:
        retry_after = settings.rate_limit_window_seconds - (
            now % settings.rate_limit_window_seconds
        )
        return False, retry_after

    return True, 0


async def enforce_rate_limit(request: Request) -> None:
    """Raise RateLimitExceededError when the client is over the rate limit."""
    from app.exceptions import RateLimitExceededError

    client_ip = get_client_ip(request)
    allowed, retry_after = await check_rate_limit(client_ip)
    if not allowed:
        raise RateLimitExceededError(
            retry_after=retry_after,
            instance=str(request.url.path),
        )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate-limit POST requests to the shorten endpoint."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path == "/api/v1/shorten" and request.method == "POST":
            client_ip = get_client_ip(request)
            allowed, retry_after = await check_rate_limit(client_ip)
            if not allowed:
                return rate_limit_exceeded_response(
                    retry_after=retry_after,
                    instance=str(request.url.path),
                )
        return await call_next(request)
