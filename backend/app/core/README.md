# app/core/

Shared, cross-cutting configuration and utilities: settings loading (from environment
variables / Azure Key Vault), structured logging, Redis connection management, and other
concerns used across layers.

**Status**:

- `config.py` — a `pydantic-settings`-based `Settings` class. Phase 1 added `ENVIRONMENT`,
  `LOG_LEVEL`, `API_HOST`, `API_PORT`, `DATABASE_URL`. The FastAPI backend application
  foundation added: `LOG_FORMAT`, `API_V1_PREFIX`, `CORS_ALLOWED_ORIGINS`/
  `CORS_ALLOW_CREDENTIALS`, database pool sizing (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`,
  `DB_POOL_TIMEOUT`, `DB_POOL_RECYCLE`), and Redis (`REDIS_URL`, `REDIS_MAX_CONNECTIONS`,
  `REDIS_SOCKET_TIMEOUT`, `REDIS_SOCKET_CONNECT_TIMEOUT`). The retailer adapter framework
  added framework-wide defaults (`RETAILER_ADAPTER_DEFAULT_*`, `RETAILER_ADAPTERS_DISABLED`).
  No secrets are hardcoded — see `.env.example`. Per-retailer credentials are added only
  alongside a real adapter, never speculatively. Phase 12 added Clerk settings
  (`CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_JWKS_URL`, `CLERK_ISSUER`,
  `CLERK_AUDIENCE`) with empty placeholders.
- `logging.py` — structured (JSON by default) logging configuration, applied once per process
  by the application factory (`app.main.create_app`).
- `redis.py` — Redis connection pool/client management and a `check_redis_connection` health
  check, consumed by `app.api.deps.get_redis` and `app.api.v1.health`. Infrastructure only — no
  caching business logic, distributed locks, or queues (those belong to later phases).

Extended incrementally as later phases need more settings (Celery, Clerk, retailer
credentials, ...).
