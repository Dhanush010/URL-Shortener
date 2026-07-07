import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import ConnectionPool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.database import Base
from app.models import ClickEvent, URL  # noqa: F401


@pytest.fixture(scope="session")
def postgres_url() -> Generator[str, None, None]:
    """Provide a PostgreSQL URL from env or a testcontainers instance."""
    env_url = os.environ.get("DATABASE_URL")
    if env_url and env_url.startswith("postgresql"):
        yield env_url
        return

    with PostgresContainer("postgres:15-alpine") as postgres:
        url = postgres.get_connection_url()
        yield url.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.fixture(scope="session")
def redis_url() -> Generator[str, None, None]:
    """Provide a Redis URL from env or a testcontainers instance."""
    env_url = os.environ.get("REDIS_URL")
    if env_url and env_url.startswith("redis"):
        yield env_url
        return

    with RedisContainer("redis:7-alpine") as redis:
        host = redis.get_container_host_ip()
        port = redis.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture(scope="session", autouse=True)
def configure_environment(postgres_url: str, redis_url: str) -> None:
    """Point the application at the test database and Redis."""
    os.environ["DATABASE_URL"] = postgres_url
    os.environ["REDIS_URL"] = redis_url
    os.environ.setdefault("BASE_URL", "http://testserver")
    os.environ.setdefault("APP_ENV", "testing")
    os.environ.setdefault("RATE_LIMIT_REQUESTS", "100")
    os.environ.setdefault("RATE_LIMIT_WINDOW_SECONDS", "60")
    os.environ.setdefault("CACHE_TTL_SECONDS", "3600")
    os.environ.setdefault("NEGATIVE_CACHE_TTL_SECONDS", "300")

    from app.config import get_settings

    get_settings.cache_clear()


@pytest.fixture(scope="session")
def event_loop():
    """Use one event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_infrastructure(
    postgres_url: str,
    redis_url: str,
    event_loop: asyncio.AbstractEventLoop,
) -> Generator[None, None, None]:
    """Patch DB/Redis clients and create schema in the test database."""
    import app.database as database
    import app.redis_client as redis_client

    engine = create_async_engine(
        postgres_url,
        poolclass=NullPool,
    )
    database.engine = engine
    database.async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    pool = ConnectionPool.from_url(
        redis_url,
        decode_responses=True,
        max_connections=20,
    )
    redis_client.pool = pool

    async def create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def teardown() -> None:
        await engine.dispose()
        await pool.disconnect()

    event_loop.run_until_complete(create_schema())
    yield
    event_loop.run_until_complete(teardown())


async def _truncate_tables() -> None:
    from app.database import engine

    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE click_events, urls RESTART IDENTITY CASCADE")
        )


@pytest_asyncio.fixture(autouse=True)
async def clean_redis() -> AsyncGenerator[None, None]:
    """Flush Redis before and after each test."""
    from app.redis_client import get_redis_client

    redis = get_redis_client()
    await redis.flushdb()
    yield
    await redis.flushdb()


@pytest_asyncio.fixture(autouse=True)
async def clean_database() -> AsyncGenerator[None, None]:
    """Reset database tables before and after each test."""
    await _truncate_tables()
    yield
    await _truncate_tables()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session for direct DB assertions."""
    from app.database import async_session_factory

    async with async_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the FastAPI app."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def sample_url() -> URL:
    """Insert a pre-existing URL row for redirect/analytics tests."""
    from app.database import async_session_factory

    async with async_session_factory() as session:
        row = URL(
            short_code="sample1",
            original_url="https://example.com/sample",
            is_active=True,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


@pytest_asyncio.fixture
async def expired_url() -> URL:
    """Insert an expired URL row."""
    from app.database import async_session_factory

    async with async_session_factory() as session:
        row = URL(
            short_code="expired1",
            original_url="https://example.com/expired",
            expires_at=datetime.now(UTC) - timedelta(days=1),
            is_active=True,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


@pytest_asyncio.fixture
async def inactive_url() -> URL:
    """Insert a deactivated URL row."""
    from app.database import async_session_factory

    async with async_session_factory() as session:
        row = URL(
            short_code="inactive",
            original_url="https://example.com/inactive",
            is_active=False,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row
