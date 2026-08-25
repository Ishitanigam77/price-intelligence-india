# backend/

Python + FastAPI backend: API layer, domain/business logic, repositories, retailer adapters,
collectors, background workers, and all price/product intelligence modules.

**Status**: **Phase 1 — Core Domain Model & Database Foundation** implemented. The domain
model, SQLAlchemy models, Alembic migrations, repositories, and a minimal FastAPI health-check
skeleton exist. Retailer adapters, collectors, normalization, matching, pricing intelligence,
sale-event intelligence, recommendation, notifications, and auth are **not** implemented yet —
see `../ROADMAP.md`.

## Layout

- `app/api/` — FastAPI routers (health check only in Phase 1)
- `app/auth/` — Clerk token verification (Phase 5+)
- `app/core/` — settings (env-var driven) and cross-cutting utilities
- `app/domain/` — framework-independent entities' invariants: enums, exceptions, validation
- `app/repositories/` — data access layer over the SQLAlchemy models
- `app/db/` — SQLAlchemy declarative base, session/engine, and ORM models (`app/db/models/`)
- `app/retailer_adapters/` — common adapter interface + per-retailer adapters (Phase 2+)
- `app/collectors/` — orchestrates data acquisition via adapters (Phase 2+)
- `app/normalization/` — raw listing → common normalized shape (Phase 3)
- `app/matching/` — product/variant matching engine (Phase 3)
- `app/pricing/` — price intelligence: effective price, history, drops (Phase 4)
- `app/sales/` — sale-event intelligence (Phase 7)
- `app/recommendation/` — BUY_NOW / WAIT / WATCH engine (Phase 9)
- `app/notifications/` — watchlist & price alert dispatch (Phase 6)
- `app/workers/` — Celery app, tasks, schedules (Phase 2+)
- `app/observability/` — structured logging, health checks, metrics
- `alembic/` — database migrations
- `scripts/seed_dev_data.py` — seeds clearly-fake development data for manually validating the
  schema (not used by the automated test suite)
- `tests/unit/`, `tests/integration/` — test suites

## Local Setup

Requires Python 3.11+ and a PostgreSQL 14+ server.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp ../.env.example ../.env   # then edit ../.env with your local DB credentials
```

Create the database and (optionally) a dedicated app role, matching whatever you put in
`DATABASE_URL` — for example:

```bash
createuser priceradar_app --pwprompt
createdb priceradar --owner=priceradar_app
createdb priceradar_test --owner=priceradar_app   # used by the integration test suite
```

## Running Migrations

`DATABASE_URL` is read from the environment (never hardcoded) by `alembic/env.py`:

```bash
export DATABASE_URL=postgresql+psycopg://priceradar_app:<password>@localhost:5432/priceradar
alembic upgrade head       # apply all migrations
alembic downgrade base     # roll back everything (verifies migrations are fully reversible)
alembic revision --autogenerate -m "describe your change"   # generate a new migration
```

## Running the API

```bash
uvicorn app.main:app --reload --host $API_HOST --port $API_PORT
```

`GET /health` is a liveness check; `GET /health/ready` additionally verifies the database is
reachable.

## Running Tests

Integration tests run against a real PostgreSQL database (set `TEST_DATABASE_URL`, or rely on
the `priceradar_test` default matching `.env.example`) and automatically migrate it to `head`
before the suite runs.

```bash
pytest                 # unit + integration tests
pytest tests/unit       # domain validation only, no database needed
```

## Seeding Fake Development Data

Optional, and only useful for manually poking at the schema (e.g. with `psql`):

```bash
python -m scripts.seed_dev_data
```

This inserts a small, clearly-fictional product/retailer/price dataset — no real retailer
names, URLs, or prices. Never run this against anything but a local/dev database.

## Linting & Formatting

```bash
ruff check .
ruff format .
```
