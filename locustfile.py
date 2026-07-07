"""
Locust load test scenarios for the URL shortener.

Traffic mix (by user-class weight):
  - ShortenUser    10%  POST /api/v1/shorten
  - RedirectUser   85%  GET /{code}
  - AnalyticsUser   5%  GET /api/v1/links/{code}/stats

Run:
  locust -f locustfile.py --host=http://localhost:8000 \\
         --users=500 --spawn-rate=50 --run-time=60s --headless \\
         --csv=results/load_test

Target:
  p50 < 5ms (cache hits), p95 < 10ms, p99 < 50ms, error rate < 0.1%
"""

from __future__ import annotations

import logging
import random

import httpx
from locust import HttpUser, between, events, task

logger = logging.getLogger(__name__)

SEED_URL_COUNT = 50
_shared_codes: list[str] = []


@events.test_start.add_listener
def seed_short_codes(environment, **kwargs) -> None:
    """Pre-create short codes so redirect/analytics traffic has targets."""
    global _shared_codes
    if _shared_codes:
        return

    host = environment.host or "http://localhost:8000"
    codes: list[str] = []

    try:
        with httpx.Client(base_url=host, timeout=30.0) as client:
            for index in range(SEED_URL_COUNT):
                response = client.post(
                    "/api/v1/shorten",
                    json={"url": f"https://loadtest.example.com/page/{index}"},
                )
                if response.status_code == 201:
                    codes.append(response.json()["short_code"])
                elif response.status_code == 429:
                    logger.warning("Rate limited while seeding at index %s", index)
                    break
    except httpx.HTTPError as exc:
        logger.error("Failed to seed short codes: %s", exc)

    _shared_codes = codes
    RedirectUser.codes = codes
    AnalyticsUser.codes = codes
    logger.info("Seeded %s short codes for load test", len(codes))


def _random_code() -> str | None:
    if not _shared_codes:
        return None
    return random.choice(_shared_codes)


class ShortenUser(HttpUser):
    """Creates new short URLs — ~10% of traffic."""

    weight = 10
    wait_time = between(0.05, 0.2)

    @task
    def shorten_url(self) -> None:
        suffix = random.randint(1, 10_000_000)
        self.client.post(
            "/api/v1/shorten",
            json={"url": f"https://loadtest.example.com/dynamic/{suffix}"},
            name="/api/v1/shorten",
        )


class RedirectUser(HttpUser):
    """Follows short links — ~85% of traffic (cache-heavy)."""

    weight = 85
    wait_time = between(0.01, 0.05)
    codes: list[str] = []

    @task
    def redirect(self) -> None:
        code = _random_code()
        if code is None:
            return
        with self.client.get(
            f"/{code}",
            name="/[code]",
            allow_redirects=False,
            catch_response=True,
        ) as response:
            if response.status_code == 301:
                response.success()
            else:
                response.failure(f"Unexpected status {response.status_code}")


class AnalyticsUser(HttpUser):
    """Reads link stats — ~5% of traffic."""

    weight = 5
    wait_time = between(0.1, 0.3)
    codes: list[str] = []

    @task
    def link_stats(self) -> None:
        code = _random_code()
        if code is None:
            return
        self.client.get(
            f"/api/v1/links/{code}/stats",
            name="/api/v1/links/[code]/stats",
        )
