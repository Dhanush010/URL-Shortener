import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.url import URL


@pytest.mark.asyncio
async def test_redirect_valid_code_returns_301(
    async_client: AsyncClient,
    sample_url: URL,
) -> None:
    response = await async_client.get(
        f"/{sample_url.short_code}",
        follow_redirects=False,
    )

    assert response.status_code == 301
    assert response.headers["location"] == sample_url.original_url


@pytest.mark.asyncio
async def test_redirect_cache_miss_then_hit(
    async_client: AsyncClient,
    sample_url: URL,
) -> None:
    first = await async_client.get(
        f"/{sample_url.short_code}",
        follow_redirects=False,
    )
    second = await async_client.get(
        f"/{sample_url.short_code}",
        follow_redirects=False,
    )

    assert first.status_code == 301
    assert first.headers.get("x-cache") == "MISS"
    assert second.status_code == 301
    assert second.headers.get("x-cache") == "HIT"
    assert second.headers["location"] == sample_url.original_url


@pytest.mark.asyncio
async def test_redirect_nonexistent_code_returns_404(async_client: AsyncClient) -> None:
    response = await async_client.get("/unknown9", follow_redirects=False)

    assert response.status_code == 404
    body = response.json()
    assert body["type"] == "https://errors.url-shortener.dev/not-found"


@pytest.mark.asyncio
async def test_redirect_expired_url_returns_410(
    async_client: AsyncClient,
    expired_url: URL,
) -> None:
    response = await async_client.get(
        f"/{expired_url.short_code}",
        follow_redirects=False,
    )

    assert response.status_code == 410
    body = response.json()
    assert body["type"] == "https://errors.url-shortener.dev/gone"


@pytest.mark.asyncio
async def test_redirect_deactivated_url_returns_410(
    async_client: AsyncClient,
    inactive_url: URL,
) -> None:
    response = await async_client.get(
        f"/{inactive_url.short_code}",
        follow_redirects=False,
    )

    assert response.status_code == 410
    assert response.json()["status"] == 410


@pytest.mark.asyncio
async def test_redirect_increments_click_count(
    async_client: AsyncClient,
    sample_url: URL,
) -> None:
    from app.database import async_session_factory

    await async_client.get(f"/{sample_url.short_code}", follow_redirects=False)
    await asyncio.sleep(0.2)

    async with async_session_factory() as session:
        result = await session.execute(
            select(URL).where(URL.short_code == sample_url.short_code)
        )
        row = result.scalar_one()
        assert row.click_count == 1


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["postgres"] == "connected"
    assert data["redis"] == "connected"
    assert data["status"] == "healthy"
