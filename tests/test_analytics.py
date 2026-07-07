import asyncio

import pytest
from httpx import AsyncClient

from app.models.url import URL


@pytest.mark.asyncio
async def test_stats_for_existing_code(
    async_client: AsyncClient,
    sample_url: URL,
) -> None:
    response = await async_client.get(f"/api/v1/links/{sample_url.short_code}/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["short_code"] == sample_url.short_code
    assert data["original_url"] == sample_url.original_url
    assert data["click_count"] == 0
    assert data["recent_clicks"] == []


@pytest.mark.asyncio
async def test_stats_for_nonexistent_code_returns_404(
    async_client: AsyncClient,
) -> None:
    response = await async_client.get("/api/v1/links/missing9/stats")

    assert response.status_code == 404
    body = response.json()
    assert body["type"] == "https://errors.url-shortener.dev/not-found"


@pytest.mark.asyncio
async def test_click_count_reflects_redirects(
    async_client: AsyncClient,
    sample_url: URL,
) -> None:
    for _ in range(3):
        await async_client.get(f"/{sample_url.short_code}", follow_redirects=False)

    await asyncio.sleep(0.3)

    response = await async_client.get(f"/api/v1/links/{sample_url.short_code}/stats")
    data = response.json()
    assert data["click_count"] == 3
    assert len(data["recent_clicks"]) == 3


@pytest.mark.asyncio
async def test_list_links_pagination(async_client: AsyncClient) -> None:
    for index in range(3):
        await async_client.post(
            "/api/v1/shorten",
            json={"url": f"https://example.com/page-{index}"},
        )

    response = await async_client.get("/api/v1/links?page=1&limit=2")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["limit"] == 2
    assert data["pages"] == 2
    assert len(data["items"]) == 2
    assert "short_url" in data["items"][0]
    assert "click_count" in data["items"][0]

    page_two = await async_client.get("/api/v1/links?page=2&limit=2")
    assert len(page_two.json()["items"]) == 1
