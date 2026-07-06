from redis.asyncio import ConnectionPool, Redis

from app.config import get_settings

settings = get_settings()

pool: ConnectionPool = ConnectionPool.from_url(
    settings.redis_url,
    decode_responses=True,
    max_connections=20,
)


def get_redis_client() -> Redis:
    """Return a Redis client backed by the shared connection pool."""
    return Redis(connection_pool=pool)


async def close_redis_pool() -> None:
    """Close the Redis connection pool on application shutdown."""
    await pool.disconnect()
