# app/db/

SQLAlchemy engine/session setup, declarative base, and ORM models. Migrations are managed
separately under `../../alembic/` and must be kept in sync with these models.

**Status**: implemented in **Phase 1 — Core Domain Model & Database Foundation**.

- `base.py` — `Base` declarative class with a naming convention applied to every
  constraint/index, so Alembic autogenerate produces stable, readable names.
- `session.py` — engine/session factory; `DATABASE_URL` is read from `app.core.config`, never
  hardcoded. Connection pool sizing (`db_pool_size`, `db_max_overflow`, `db_pool_timeout`,
  `db_pool_recycle`) is also read from `Settings`, added as part of the FastAPI backend
  application foundation.
- `models/` — one module per entity: `Category`, `Brand`, `Product`, `ProductVariant`,
  `ProductIdentifier`, `Retailer`, `Seller`, `RetailerProduct`, `PriceSnapshot`. See each
  module's docstring for the reasoning behind its shape and constraints.
