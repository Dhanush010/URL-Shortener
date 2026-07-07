# URL Shortener

Production-quality URL shortener built with FastAPI, PostgreSQL, and Redis.

## Features

- Async FastAPI API with RFC 7807 error responses
- PostgreSQL persistence (SQLAlchemy 2.0 + asyncpg)
- Redis cache-aside for hot redirects
- Sliding-window rate limiting (100 req/min per IP)
- Click analytics with async event logging
- Paginated URL listing
- Alembic migrations, Pytest + testcontainers, Locust load tests

## Quick start (local)

```bash
docker-compose up --build
```

Verify:

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

API docs: http://localhost:8000/docs

## Run tests

```bash
# Recommended — isolated test Postgres + Redis
docker-compose -f docker-compose.test.yml run --rm test

# Or with local Python 3.11 + Docker (testcontainers)
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v --cov=app --cov-fail-under=80
```

## Load testing (Locust)

Start the app, flush rate-limit counters, then run a load test:

```bash
docker-compose up --build -d
docker-compose exec redis redis-cli FLUSHDB

# Full mixed workload (500 users, 60s) — stress test
docker-compose --profile loadtest run --rm loadtest

# Cache-heavy redirect benchmark (100 users, 30s)
LOCUST_USER_CLASS=RedirectUser LOCUST_USERS=100 LOCUST_SPAWN_RATE=25 \
  LOCUST_RUN_TIME=30s LOCUST_CSV_PREFIX=results/load_test_redirect \
  docker-compose --profile loadtest run --rm loadtest
```

On Windows (Git Bash or WSL): `./scripts/run_load_test.sh` or `./scripts/run_load_test.sh redirect`

Results land in `results/load_test_stats.csv` (and `results/load_test_failures.csv`).

### Targets and local results

| Scenario | Users | p50 | p95 | Error rate | Notes |
|----------|-------|-----|-----|------------|-------|
| Redirect-only (cache warm) | 20 | ~99 ms | ~220 ms | 0% | Local Docker, single uvicorn worker |
| Redirect-only (cache warm) | 100 | ~180 ms | ~670 ms | ~7% | DB pool pressure from async click logging |
| Mixed (shorten + redirect + analytics) | 500 | ~410 ms | ~15 s | ~8% | POST rate limits + dev resource limits |

**Design target:** p95 &lt; 10 ms on cache hits in production (Redis-only redirect path, no DB session opened on cache hit).

Local Docker will be slower than Railway because of single-worker uvicorn, click-event writes under load, and container overhead. Re-run the redirect benchmark after deploy to validate production latency.

## Deploy to Railway

1. Push this repo to GitHub (see commands below).
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**.
3. Add the **PostgreSQL** plugin → Railway sets `DATABASE_URL` (convert to `postgresql+asyncpg://...` if needed).
4. Add the **Redis** plugin → Railway sets `REDIS_URL`.
5. Set environment variables:

   | Variable | Value |
   |----------|-------|
   | `APP_ENV` | `production` |
   | `BASE_URL` | `https://your-app.up.railway.app` |
   | `SECRET_KEY` | strong random secret |
   | `DATABASE_URL` | `postgresql+asyncpg://...` (async driver) |

6. Railway detects the `Dockerfile` and deploys. Migrations run on startup via `alembic upgrade head`.
7. Smoke test:

   ```bash
   curl https://your-app.up.railway.app/health
   curl -X POST https://your-app.up.railway.app/api/v1/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}'
   ```

## CI

GitHub Actions runs on every push/PR to `main` or `master`:

- Installs dependencies
- Runs `pytest` with ≥ 80% coverage (testcontainers on ubuntu-latest)

## Tech stack

- FastAPI (Python 3.11)
- PostgreSQL 15 (async SQLAlchemy 2.0 + asyncpg)
- Redis 7 (redis-py async)
- Alembic, Pytest + testcontainers, Locust, Docker, Railway
