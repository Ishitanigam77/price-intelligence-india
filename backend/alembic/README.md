# alembic/

Alembic migration environment and versioned migration scripts for the PostgreSQL schema.

**Status**: implemented in **Phase 1 — Core Domain Model & Database Foundation**.

`env.py` reads the database URL from `DATABASE_URL` via `app.core.config.get_settings()` — it
is never hardcoded here or in `alembic.ini`. `versions/0001_phase1_core_domain_schema.py`
creates the Phase 1 schema (`categories`, `brands`, `products`, `product_variants`,
`product_identifiers`, `retailers`, `sellers`, `retailer_products`, `price_snapshots`) with its
indexes, foreign keys, unique constraints, and check constraints. See `../README.md` for the
commands to run migrations.
