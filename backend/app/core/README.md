# app/core/

Shared, cross-cutting configuration and utilities: settings loading (from environment
variables / Azure Key Vault), shared exceptions, and other concerns used across layers.

**Status**: `config.py` implemented in **Phase 1** — a `pydantic-settings`-based `Settings`
class reading `ENVIRONMENT`, `LOG_LEVEL`, `API_HOST`, `API_PORT`, and `DATABASE_URL` from the
environment (see `.env.example`). No secrets are hardcoded. Extended incrementally as later
phases need more settings (Redis, Celery, Clerk, retailer credentials, ...).
