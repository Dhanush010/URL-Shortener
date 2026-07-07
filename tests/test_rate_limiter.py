import asyncio

import pytest
from httpx import AsyncClient

from app.services.rate_limiter import check_rate_limit


@pytest.mark.asyncio
async def test_rate_limit_allows_up_to_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_requests", 5)

    for i in range(5):
        allowed, retry_after = await check_rate_limit(f"test-ip-allowed-{i}")
        assert allowed is True
        assert retry_after == 0


@pytest.mark.asyncio
async def test_rate_limit_blocks_over_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_requests", 5)
    client_ip = "test-ip-blocked"

    for _ in range(5):
        allowed, _ = await check_rate_limit(client_ip)
        assert allowed is True

    allowed, retry_after = await check_rate_limit(client_ip)
    assert allowed is False
    assert 1 <= retry_after <= settings.rate_limit_window_seconds


@pytest.mark.asyncio
async def test_rate_limit_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_requests", 2)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 1)
    client_ip = "test-ip-reset"

    assert (await check_rate_limit(client_ip))[0] is True
    assert (await check_rate_limit(client_ip))[0] is True
    assert (await check_rate_limit(client_ip))[0] is False

    await asyncio.sleep(1.1)

    allowed, retry_after = await check_rate_limit(client_ip)
    assert allowed is True
    assert retry_after == 0


@pytest.mark.asyncio
async def test_rate_limit_different_ips_have_separate_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_requests", 2)

    assert (await check_rate_limit("ip-a"))[0] is True
    assert (await check_rate_limit("ip-a"))[0] is True
    assert (await check_rate_limit("ip-a"))[0] is False

    allowed, _ = await check_rate_limit("ip-b")
    assert allowed is True


@pytest.mark.asyncio
async def test_rate_limit_middleware_returns_retry_after_header(
    async_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_requests", 2)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)

    payload = {"url": "https://example.com/rl-header"}
    headers = {"X-Forwarded-For": "10.0.0.99"}

    await async_client.post("/api/v1/shorten", json=payload, headers=headers)
    await async_client.post("/api/v1/shorten", json=payload, headers=headers)

    blocked = await async_client.post(
        "/api/v1/shorten",
        json=payload,
        headers=headers,
    )

    assert blocked.status_code == 429
    retry_after = int(blocked.headers["retry-after"])
    body_retry = blocked.json()["retry_after"]
    assert 1 <= retry_after <= 60
    assert body_retry == retry_after
