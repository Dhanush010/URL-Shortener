# URL Shortener

Production-quality URL shortener built with FastAPI, PostgreSQL, and Redis.

## Phase 1 — Foundation (current)

- Project structure, config, async database, Redis client
- SQLAlchemy URL model
- Alembic migrations for `urls` and `click_events` tables
- Docker Compose for local development

### Quick start

```bash
docker-compose up --build
```

Verify health:

```bash
curl http://localhost:8000/health
```

Verify tables:

```bash
docker-compose exec postgres psql -U user -d urlshortener -c "\dt"
```

## Tech stack

- FastAPI (Python 3.11)
- PostgreSQL 15 (async SQLAlchemy 2.0 + asyncpg)
- Redis 7 (redis-py async)
- Alembic, Pytest + testcontainers, Locust, Railway
