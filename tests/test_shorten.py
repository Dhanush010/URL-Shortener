import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_shorten_valid_url_returns_201(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/shorten",
        json={"url": "https://www.example.com/very/long/path"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "short_code" in data
    assert len(data["short_code"]) == 6
    assert data["original_url"] == "https://www.example.com/very/long/path"
    assert data["short_url"].startswith("http://testserver/")
    assert data["expires_at"] is None


@pytest.mark.asyncio
async def test_shorten_invalid_url_returns_422_rfc7807(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/shorten",
        json={"url": "ftp://not-valid.com"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == "https://errors.url-shortener.dev/invalid-url"
    assert body["title"] == "Invalid URL"
    assert body["status"] == 422
    assert body["instance"] == "/api/v1/shorten"


@pytest.mark.asyncio
async def test_shorten_duplicate_custom_code_returns_409(async_client: AsyncClient) -> None:
    payload = {"url": "https://example.com/a", "custom_code": "mylink"}

    first = await async_client.post("/api/v1/shorten", json=payload)
    assert first.status_code == 201

    second = await async_client.post("/api/v1/shorten", json=payload)
    assert second.status_code == 409
    body = second.json()
    assert body["type"] == "https://errors.url-shortener.dev/conflict"
    assert "mylink" in body["detail"]


@pytest.mark.asyncio
async def test_shorten_invalid_custom_code_returns_422(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com", "custom_code": "bad code!"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "https://errors.url-shortener.dev/invalid-custom-code"


@pytest.mark.asyncio
async def test_shorten_with_expires_in_days(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com", "expires_in_days": 30},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_shorten_same_url_twice_generates_different_codes(
    async_client: AsyncClient,
) -> None:
    payload = {"url": "https://example.com/same"}

    first = await async_client.post("/api/v1/shorten", json=payload)
    second = await async_client.post("/api/v1/shorten", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["short_code"] != second.json()["short_code"]


@pytest.mark.asyncio
async def test_shorten_rate_limit_exceeded_returns_429(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import get_settings
    from app.redis_client import get_redis_client

    await get_redis_client().flushdb()
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_requests", 2)

    payload = {"url": "https://example.com/rate-limit"}
    headers = {"X-Forwarded-For": "10.0.0.55"}

    for _ in range(2):
        response = await async_client.post(
            "/api/v1/shorten",
            json=payload,
            headers=headers,
        )
        assert response.status_code == 201

    blocked = await async_client.post(
        "/api/v1/shorten",
        json=payload,
        headers=headers,
    )
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["type"] == "https://errors.url-shortener.dev/rate-limited"
    assert "retry_after" in body
    assert blocked.headers.get("retry-after") is not None


@pytest.mark.asyncio
async def test_shorten_response_short_url_uses_base_url(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/shorten",
        json={"url": "https://example.com/base"},
    )

    data = response.json()
    assert data["short_url"] == f"http://testserver/{data['short_code']}"
