# tests/integration/

Integration tests spanning multiple components (e.g. API + database, collector + adapter with
recorded fixtures). Added alongside the real logic they cover, starting in **Phase 1**.

Phase 1's suite runs against a real PostgreSQL database (`conftest.py` migrates it to `head`
automatically) and covers: every entity's constraints (uniqueness, check constraints, cascades,
partial unique indexes), the repository layer, the Alembic migration chain (upgrade/downgrade
round-trip), and the FastAPI health check endpoints. See `../../README.md` for how to point
tests at your own database via `TEST_DATABASE_URL`.
