# backend/

Python + FastAPI backend: API layer, domain/business logic, repositories, retailer adapters,
collectors, background workers, and all price/product intelligence modules.

**Status**: **Phase 1 — Core Domain Model & Database Foundation** implemented (domain model,
SQLAlchemy models, Alembic migrations, repositories), plus a **FastAPI backend application
foundation** — application factory, startup/shutdown lifecycle, `/api/v1/` versioned routing,
Redis infrastructure, centralized exception handling, structured logging, CORS, and Docker
support — and the **retailer adapter framework** (common interface, registry, execution
helpers, and three fixture-backed mock adapters). The **product identity matching engine**
(`app/matching/`) and **price comparison engine** (`app/pricing/`,
`GET /api/v1/products/{product_id}/prices`) are implemented. **Phase 9 sale-event intelligence**
(`app/sales/`, `GET /api/v1/sale-events`, `GET /api/v1/products/{id}/sale-history`) is
implemented. **Phase 10 sale-price prediction** (`ml/`, `GET /api/v1/products/{id}/sale-price-prediction`)
is implemented. **Phase 11 BUY / WAIT recommendation** (`app/recommendation/`,
`GET /api/v1/products/{id}/recommendation`) is implemented. **Phase 12 Clerk authentication
and personalization** (`app/auth/`, `/api/v1/me`, watchlists, saved products, target prices,
alerts) is implemented. Collectors, real retailer integrations, and notification dispatch are
**not** implemented yet — see `../ROADMAP.md`.

> **Note on phase numbering**: `../ROADMAP.md` reserves "Phase 2" for the Retailer Adapter
> Framework. That framework is implemented here (`app/retailer_adapters/`). A separate
> FastAPI application-foundation increment (application factory, `/api/v1/`, Redis, Docker)
> was merged independently and is also present.

## Layout

- `app/api/` — FastAPI routers and DTOs. `health.py` is the unversioned Phase 1 liveness/
  readiness check (kept for backward compatibility / simple orchestrator probes); `v1/` is the
  versioned API (see below). `deps.py` wires repositories/services into routes via dependency
  injection; `errors.py` is the centralized exception handling.
- `app/api/v1/` — `/api/v1/` routers: `health` (liveness + per-dependency readiness),
  `products` (catalogue + `GET /products/search` discovery + prices/history/sale-history/
  sale-price-prediction/recommendation), `retailers`, `prices`, `deals`, `sale_events`,
  `me`, `watchlists`, `saved_products`, `target_prices`, `alerts`.
- `app/schemas/` — Pydantic request/response DTOs, kept separate from the SQLAlchemy models.
- `app/services/` — thin service-layer boundaries, added only where genuinely needed:
  `price_service.py` (listing vs observation existence) and `product_discovery_service.py`
  (retailer-agnostic search → normalize → persist → respond).
- `app/auth/` — Clerk token verification and internal user mapping (Phase 12)
- `app/core/` — settings (env-var driven: API, database, Redis, CORS, logging, Clerk, and retailer
  adapter defaults), structured logging setup, and Redis connection/client management.
- `app/domain/` — framework-independent entities' invariants: enums, exceptions, validation
- `app/repositories/` — data access layer over the SQLAlchemy models
- `app/db/` — SQLAlchemy declarative base, session/engine (pool-configurable), and ORM models
  (`app/db/models/`)
- `app/retailer_adapters/` — common adapter interface, registry, execution helpers, and
  fixture-backed mock adapters (Phase 2). Real retailer integrations are later.
- `app/collectors/` — orchestrates data acquisition via adapters (later; the adapter
  framework is in place)
- `app/normalization/` — raw listing → common normalized shape (Phase 3)
- `app/matching/` — product/variant matching engine (this increment): four-stage pipeline
  (exact identifiers, normalized attributes, title/token similarity, embeddings). Independent
  of FastAPI routes and of specific retailer adapters.
- `app/pricing/` — price comparison engine (Phase 6) and historical price intelligence
  (Phase 7: window averages, extrema, percentile, volatility, drop detection, trend)
- `app/sales/` — sale-event intelligence (Phase 9)
- `app/recommendation/` — BUY_NOW / WAIT / WATCH engine (Phase 11)
- `app/notifications/` — watchlist & price alert dispatch (Phase 6)
- `app/workers/` — Celery app, tasks, schedules (Phase 2+)
- `app/observability/` — structured JSON logging, correlation IDs, metrics seams
- `alembic/` — database migrations
- `Dockerfile`, `docker-entrypoint.sh`, `.dockerignore` — production-oriented backend image
- `scripts/seed_dev_data.py` — seeds clearly-fake development data for manually validating the
  schema (not used by the automated test suite)
- `scripts/train_sale_price_model.py` — offline Phase 10 training from stored observations
  and sale events (`INSUFFICIENT_DATA` if history is inadequate; never fabricates rows)
- `tests/unit/`, `tests/integration/` — test suites

See also `../infrastructure/docker/docker-compose.yml` for the local development stack
(backend + PostgreSQL + Redis).

## Local Setup

Requires Python 3.11+ and a PostgreSQL 14+ server.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp ../.env.example ../.env   # then edit ../.env with your local DB/Redis credentials
```

Create the database and (optionally) a dedicated app role, matching whatever you put in
`DATABASE_URL` — for example:

```bash
createuser priceradar_app --pwprompt
createdb priceradar --owner=priceradar_app
createdb priceradar_test --owner=priceradar_app   # used by the integration test suite
```

### Redis

A local Redis instance is required for the readiness check and for the Redis connectivity
tests. Install/run it however you prefer, e.g.:

```bash
sudo apt-get install redis-server && sudo service redis-server start
# or: docker run --rm -p 6379:6379 redis:7-alpine
```

`REDIS_URL` (see `.env.example`) defaults to `redis://localhost:6379/0`.

## Running Migrations

`DATABASE_URL` is read from the environment (never hardcoded) by `alembic/env.py`:

```bash
export DATABASE_URL=postgresql+psycopg://priceradar_app:<password>@localhost:5432/priceradar
alembic upgrade head       # apply all migrations
alembic downgrade base     # roll back everything (verifies migrations are fully reversible)
alembic revision --autogenerate -m "describe your change"   # generate a new migration
```

No Phase 2 schema changes were introduced — the existing Phase 1 migration
(`0001_phase1_core_domain_schema`) is unchanged.

## Running the API

```bash
uvicorn app.main:app --reload --host $API_HOST --port $API_PORT
```

- `GET /health` / `GET /health/ready` — Phase 1 liveness/readiness (unversioned, kept for
  backward compatibility and simple container/orchestrator probes).
- `GET /api/v1/health` / `GET /api/v1/health/ready` — versioned liveness/readiness. Readiness
  reports PostgreSQL and Redis availability independently and returns HTTP 503 (with a
  structured body identifying which dependency is down) if either is unreachable.
- `GET /api/v1/products`, `/api/v1/products/search`, `/api/v1/products/{id}/prices`,
  `/api/v1/products/{id}/history`, `/api/v1/retailers`, `/api/v1/prices/...`, `/api/v1/deals` —
  catalogue foundation, Phase 4 product discovery, Phase 6 price comparison, and Phase 7
  historical price intelligence (see `app/api/v1/`).
- Interactive API docs: `GET /docs` (Swagger UI), `GET /redoc` (ReDoc), `GET /openapi.json`.

## Running Tests

Integration tests run against a real PostgreSQL database (set `TEST_DATABASE_URL`, or rely on
the `priceradar_test` default matching `.env.example`) and automatically migrate it to `head`
before the suite runs. A local Redis instance (`REDIS_URL`, default
`redis://localhost:6379/0`) is required for the Redis/readiness tests.

```bash
pytest                 # unit + integration tests
pytest tests/unit       # domain validation + settings, no database/Redis needed
```

## Docker / Docker Compose

A production-oriented `Dockerfile` (multi-stage build, non-root user, container health check)
lives at `backend/Dockerfile`. For local development, `infrastructure/docker/docker-compose.yml`
brings up the backend alongside PostgreSQL (with a persistent volume) and Redis:

```bash
cp .env.example .env   # from the repo root; edit with your own local values
cd infrastructure/docker
docker compose up --build
```

The backend container applies Alembic migrations on startup by default (see
`docker-entrypoint.sh`); set `RUN_DB_MIGRATIONS=false` to disable that (e.g. when migrations are
run as their own deployment step). This is local development tooling only — production
Azure/Kubernetes deployment is out of scope until `../ROADMAP.md` Phase 11.

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
