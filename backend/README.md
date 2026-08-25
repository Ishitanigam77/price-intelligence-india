# backend/

Python + FastAPI backend: API layer, domain/business logic, repositories, retailer adapters,
collectors, background workers, and all price/product intelligence modules.

**Status**: empty scaffold. See `../PROJECT_ARCHITECTURE.md` for the layer breakdown and
`../ROADMAP.md` for when each subdirectory is populated. No application code exists here yet.

## Layout

- `app/api/` — FastAPI routers (Phase 1+)
- `app/auth/` — Clerk token verification (Phase 5+)
- `app/core/` — settings and cross-cutting utilities
- `app/domain/` — Product / Variant / Listing / Seller / Observation entities (Phase 1)
- `app/repositories/` — data access layer (Phase 1+)
- `app/db/` — SQLAlchemy session/base setup (Phase 1+)
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
- `alembic/` — database migrations (Phase 1+)
- `tests/unit/`, `tests/integration/` — test suites, added alongside real logic
