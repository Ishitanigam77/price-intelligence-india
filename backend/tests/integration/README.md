# tests/integration/

Integration tests spanning multiple components (e.g. API + database, collector + adapter with
recorded fixtures). Added alongside the real logic they cover, starting in **Phase 1**.

Phase 1's suite runs against a real PostgreSQL database (`conftest.py` migrates it to `head`
automatically) and covers: every entity's constraints (uniqueness, check constraints, cascades,
partial unique indexes), the repository layer, the Alembic migration chain (upgrade/downgrade
round-trip), and the FastAPI health check endpoints. See `../../README.md` for how to point
tests at your own database via `TEST_DATABASE_URL`.

The FastAPI backend application foundation added: `test_app_factory.py` (application
startup/shutdown, CORS, mounted routes), `test_database_connectivity.py` and
`test_redis_connectivity.py` (dependency connectivity, including graceful failure), `test_deps.py`
(dependency-injection wiring), `test_exception_handling.py` (centralized error handling, using
an isolated test app), `test_v1_health_endpoint.py` (versioned liveness/readiness, including
simulated PostgreSQL/Redis outages), and `test_api_products.py`/`test_api_retailers.py`/
`test_api_prices.py`/`test_api_deals.py` (representative `/api/v1/` route tests, via the
`client` fixture in `conftest.py`). These require a local Redis instance in addition to the
Phase 1 PostgreSQL requirement — see `../../README.md`.
