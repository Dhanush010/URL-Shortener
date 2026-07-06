import json
from dataclasses import dataclass

from app.config import get_settings
from app.redis_client import get_redis_client

CACHE_KEY_PREFIX = "url:"
EXPIRED_MARKER = "EXPIRED"


@dataclass(frozen=True)
class CachedURL:
    """A URL entry retrieved from the Redis cache."""

    original_url: str
    is_active: bool


@dataclass(frozen=True)
class CachedExpired:
    """Negative cache marker for expired or deactivated URLs."""

    expired: bool = True


CacheEntry = CachedURL | CachedExpired


def _cache_key(short_code: str) -> str:
    return f"{CACHE_KEY_PREFIX}{short_code}"


async def get(short_code: str) -> CacheEntry | None:
    """Return a cached URL entry, or None on cache miss."""
    redis = get_redis_client()
    raw = await redis.get(_cache_key(short_code))

    if raw is None:
        return None

    if raw == EXPIRED_MARKER:
        return CachedExpired()

    data = json.loads(raw)
    return CachedURL(
        original_url=data["original_url"],
        is_active=data["is_active"],
    )


async def set(
    short_code: str,
    *,
    original_url: str,
    is_active: bool,
    ttl: int | None = None,
) -> None:
    """Store an active URL in the cache."""
    settings = get_settings()
    redis = get_redis_client()
    payload = json.dumps({"original_url": original_url, "is_active": is_active})
    await redis.set(
        _cache_key(short_code),
        payload,
        ex=ttl or settings.cache_ttl_seconds,
    )


async def set_negative(short_code: str, ttl: int | None = None) -> None:
    """Store a negative cache entry for expired or deactivated URLs."""
    settings = get_settings()
    redis = get_redis_client()
    await redis.set(
        _cache_key(short_code),
        EXPIRED_MARKER,
        ex=ttl or settings.negative_cache_ttl_seconds,
    )


async def invalidate(short_code: str) -> None:
    """Remove a short code from the cache."""
    redis = get_redis_client()
    await redis.delete(_cache_key(short_code))
