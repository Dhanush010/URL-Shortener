from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError
from app.models.url import URL
from app.services import cache_service
from app.services.url_service import (
    build_short_url,
    create_short_url,
    get_url_stats,
    hash_client_ip,
    is_url_expired,
    list_urls,
)
from app.utils.shortcode import generate_short_code, generate_unique_short_code


def test_generate_short_code_default_length() -> None:
    code = generate_short_code()
    assert len(code) == 6
    assert code.isalnum()


@pytest.mark.asyncio
async def test_generate_unique_short_code(db_session: AsyncSession) -> None:
    code = await generate_unique_short_code(db_session)
    assert len(code) == 6

    duplicate = await generate_unique_short_code(db_session)
    assert code != duplicate


def test_build_short_url() -> None:
    assert build_short_url("abc123") == "http://testserver/abc123"


def test_hash_client_ip_is_deterministic() -> None:
    first = hash_client_ip("192.168.1.1")
    second = hash_client_ip("192.168.1.1")
    assert first == second
    assert len(first) == 64


def test_is_url_expired_false_when_no_expiry() -> None:
    row = URL(
        short_code="code1",
        original_url="https://example.com",
        expires_at=None,
    )
    assert is_url_expired(row) is False


def test_is_url_expired_true_when_past() -> None:
    row = URL(
        short_code="code2",
        original_url="https://example.com",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    assert is_url_expired(row) is True


@pytest.mark.asyncio
async def test_create_short_url_with_custom_code(db_session: AsyncSession) -> None:
    row = await create_short_url(
        db_session,
        original_url="https://example.com/custom",
        custom_code="custom01",
    )
    await db_session.commit()

    assert row.short_code == "custom01"
    assert row.original_url == "https://example.com/custom"


@pytest.mark.asyncio
async def test_create_short_url_duplicate_custom_code_raises(
    db_session: AsyncSession,
) -> None:
    await create_short_url(
        db_session,
        original_url="https://example.com/one",
        custom_code="dupcode1",
    )
    await db_session.commit()

    with pytest.raises(ConflictError):
        await create_short_url(
            db_session,
            original_url="https://example.com/two",
            custom_code="dupcode1",
        )


@pytest.mark.asyncio
async def test_get_url_stats_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await get_url_stats(db_session, "missing9")


@pytest.mark.asyncio
async def test_list_urls_returns_pagination(db_session: AsyncSession) -> None:
    for index in range(3):
        db_session.add(
            URL(
                short_code=f"list{index}",
                original_url=f"https://example.com/{index}",
                is_active=True,
            )
        )
    await db_session.commit()

    items, total, page, limit, pages = await list_urls(
        db_session,
        page=1,
        limit=2,
    )

    assert total == 3
    assert len(items) == 2
    assert page == 1
    assert limit == 2
    assert pages == 2


@pytest.mark.asyncio
async def test_cache_service_round_trip() -> None:
    await cache_service.set(
        "cache01",
        original_url="https://example.com/cached",
        is_active=True,
        ttl=60,
    )

    cached = await cache_service.get("cache01")
    assert cached is not None
    assert cached.original_url == "https://example.com/cached"
    assert cached.is_active is True

    await cache_service.invalidate("cache01")
    assert await cache_service.get("cache01") is None


@pytest.mark.asyncio
async def test_cache_service_negative_entry() -> None:
    await cache_service.set_negative("gone01", ttl=60)

    cached = await cache_service.get("gone01")
    from app.services.cache_service import CachedExpired

    assert isinstance(cached, CachedExpired)
