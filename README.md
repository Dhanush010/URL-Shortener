# URL Shortener

A production-quality, rate-limited URL shortener API built with FastAPI, PostgreSQL, and Redis.
Deployed live on Render with managed Supabase (PostgreSQL) and Upstash (Redis).

**Live API:** https://url-shortener-autr.onrender.com  
**API Docs (Swagger):** https://url-shortener-autr.onrender.com/docs

---

## Features

- **URL shortening** — auto-generated base62 codes or custom aliases
- **Fast redirects** — Redis cache-aside pattern; cache hits bypass PostgreSQL entirely
- **Rate limiting** — sliding-window counter (100 req/min per IP) enforced via Redis
- **Click analytics** — per-redirect click logging with IP hashing (SHA-256 + salt)
- **Paginated listing** — browse all shortened URLs with metadata
- **RFC 7807 errors** — all error responses follow Problem Details standard
- **91% test coverage** — 36 tests with real PostgreSQL and Redis via testcontainers
- **Load tested** — validated at 500 concurrent users; p95 < 10ms on cache hits

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI, Python 3.11, Uvicorn |
| **Database** | PostgreSQL 15, SQLAlchemy 2.0 (async), asyncpg, Alembic |
| **Cache & Rate Limiting** | Redis 7, redis-py (async) |
| **Testing** | Pytest, testcontainers, pytest-cov (91% coverage) |
| **Load Testing** | Locust |
| **DevOps** | Docker, Docker Compose, GitHub Actions CI |
| **Deployment** | Render (app), Supabase (PostgreSQL), Upstash (Redis) |

---

## Architecture

```
Client
  │
  ├── POST /api/v1/shorten
  │     └── Rate Limit (Redis sliding window)
  │           └── Insert → PostgreSQL (urls table)
  │
  ├── GET /{code}
  │     └── Redis cache lookup
  │           ├── HIT  → 301 redirect (X-Cache: HIT)
  │           └── MISS → PostgreSQL lookup → cache → 301 redirect
  │                         └── background task: log click → PostgreSQL
  │
  └── GET /api/v1/links/{code}/stats
        └── PostgreSQL (click_events table)

Data stores:
  Supabase (PostgreSQL) — urls, click_events
  Upstash (Redis)       — URL cache, rate limit counters
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | PostgreSQL + Redis connectivity check |
| `POST` | `/api/v1/shorten` | Create a short URL |
| `GET` | `/{code}` | Redirect to original URL (301) |
| `GET` | `/api/v1/links/{code}/stats` | Click count + recent click history |
| `GET` | `/api/v1/links` | Paginated list of all URLs |
| `GET` | `/docs` | Swagger UI (interactive API explorer) |

### POST /api/v1/shorten

```bash
curl -X POST https://url-shortener-autr.onrender.com/api/v1/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/very/long/url", "expires_in_days": 30}'
```

```json
{
  "short_code": "abc123",
  "short_url": "https://url-shortener-autr.onrender.com/abc123",
  "original_url": "https://example.com/very/long/url",
  "created_at": "2026-07-06T10:00:00Z",
  "expires_at": "2026-08-05T10:00:00Z"
}
```

### GET /{code}

```bash
curl -L https://url-shortener-autr.onrender.com/abc123
# → 301 redirect to original URL
# Response header: X-Cache: HIT or MISS
```

### GET /api/v1/links/{code}/stats

```bash
curl https://url-shortener-autr.onrender.com/api/v1/links/abc123/stats
```

```json
{
  "short_code": "abc123",
  "original_url": "https://example.com/very/long/url",
  "click_count": 42,
  "created_at": "2026-07-06T10:00:00Z",
  "expires_at": "2026-08-05T10:00:00Z",
  "recent_clicks": [
    { "clicked_at": "2026-07-06T12:30:00Z", "user_agent": "Mozilla/5.0..." }
  ]
}
```

---

## Design Decisions

**Why Redis cache-aside instead of write-through?**  
Redirect lookups are read-heavy (~85% of traffic). Cache-aside only populates on miss, avoiding unnecessary writes for URLs that are never accessed. TTL expiry handles cache invalidation naturally without a separate invalidation step.

**Why sliding-window rate limiting instead of token bucket?**  
Sliding window prevents burst abuse at window boundaries (a known weakness of fixed-window counters) while being implementable with a single Redis INCR + EXPIRE — no Lua scripting required.

**Why async SQLAlchemy + asyncpg?**  
FastAPI is async-native. Using synchronous SQLAlchemy would block the event loop under load. asyncpg is the fastest PostgreSQL driver in Python and pairs directly with SQLAlchemy 2.0's async engine.

**Why testcontainers instead of mocks?**  
Mocking Redis and PostgreSQL at the client level would test the wrong thing — it tests that our mock behaves correctly, not that our code works against real databases. testcontainers spins up actual Docker containers per test session, making tests production-equivalent.

---

## Local Development

### Prerequisites
- Docker + Docker Compose
- Python 3.11+

### Setup

```bash
git clone https://github.com/Dhanush010/URL-Shortener
cd URL-Shortener

# Copy env file
cp .env.example .env

# Start app + PostgreSQL + Redis
docker-compose up --build

# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```

### Run migrations manually

```bash
docker-compose exec app alembic upgrade head
```

---

## Testing

```bash
# Run full test suite with coverage
docker-compose -f docker-compose.test.yml run --rm test

# Or locally (requires Python 3.11 + Docker for testcontainers)
pip install -r requirements-dev.txt
pytest tests/ -v --cov=app --cov-report=term-missing
```

**Coverage: 91%** (requirement: ≥80%)

| Test file | What it covers |
|---|---|
| `test_shorten.py` | URL creation, custom codes, validation, collision handling |
| `test_redirect.py` | Cache hit/miss, click count, expired/deactivated URLs |
| `test_rate_limiter.py` | Window limits, per-IP isolation, Retry-After header |
| `test_analytics.py` | Stats endpoint, pagination, click logging |
| `test_url_service.py` | Service layer unit tests |

---

## Load Testing

```bash
# Seed URLs then run Locust (500 users, 60 seconds)
docker-compose exec redis redis-cli FLUSHDB
docker-compose --profile loadtest run --rm loadtest

# Or manually
python scripts/seed_urls.py http://localhost:8000 100
locust -f locustfile.py --host=http://localhost:8000 \
       --users=500 --spawn-rate=50 --run-time=60s --headless
```

**Traffic distribution:**
- 85% `GET /{code}` redirects (cache-heavy)
- 10% `POST /api/v1/shorten` (rate-limit tested)
- 5% `GET /stats` (DB reads)

**Results (local, 500 concurrent users):**
- p50 latency: ~3ms (cache hits)
- p95 latency: <10ms
- Error rate: <0.1%

---

## Deployment

Deployed on **Render** (app) + **Supabase** (PostgreSQL) + **Upstash** (Redis).

Key production config:
- Alembic migrations run automatically on container start
- Supabase session pooler used for asyncpg compatibility
- Upstash Redis over TLS (`rediss://`)
- IP hashing uses `SECRET_KEY` env var for privacy

See `.env.production.example` for all required environment variables.

---

## CI/CD

GitHub Actions runs on every push and pull request:

```
✅ Install dependencies
✅ Run pytest with testcontainers
✅ Enforce ≥80% coverage (fails build if below)
```

---

## Project Structure

```
url-shortener/
├── app/
│   ├── main.py              # FastAPI app, health endpoint, middleware
│   ├── config.py            # Pydantic settings from env vars
│   ├── database.py          # Async SQLAlchemy engine + session
│   ├── redis_client.py      # Redis connection pool
│   ├── exceptions.py        # RFC 7807 error responses
│   ├── api/v1/
│   │   ├── shorten.py       # POST /api/v1/shorten
│   │   ├── redirect.py      # GET /{code}
│   │   └── analytics.py     # Stats + paginated list
│   ├── models/              # SQLAlchemy models (URL, ClickEvent)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/
│   │   ├── url_service.py   # Business logic
│   │   ├── cache_service.py # Cache-aside pattern
│   │   └── rate_limiter.py  # Sliding window rate limiter
│   └── utils/shortcode.py   # Base62 code generation
├── migrations/              # Alembic migrations
├── tests/                   # 36 tests, 91% coverage
├── scripts/                 # Seed URLs, load test runners
├── locustfile.py            # Locust load test scenarios
├── docker-compose.yml       # Dev + loadtest profiles
├── Dockerfile
└── .github/workflows/ci.yml # GitHub Actions CI
```
