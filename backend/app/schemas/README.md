# app/schemas/

Pydantic API request/response schemas (DTOs), introduced as part of the FastAPI backend
application foundation.

**Status**: FastAPI backend application foundation.

- `common.py` — `Page[T]` (generic pagination envelope) and the `ErrorResponse`/`ErrorDetail`
  shape returned by every centralized exception handler (see `app/api/errors.py`).
- `pagination.py` — the shared `limit`/`offset` query-parameter dependency used by every list
  route.
- `product.py`, `retailer.py`, `price.py` — read schemas mirroring the Phase 1 `Product`/
  `ProductVariant`/`Brand`/`Category`, `Retailer`/`Seller`, and `PriceSnapshot` models,
  respectively, but as plain DTOs independent of SQLAlchemy.
- `discovery.py` — search-result DTOs for `GET /api/v1/products/search` (product, variant,
  retailer, seller, observed price/availability, source URL, observation timestamp).
- `comparison.py` — DTOs for `GET /api/v1/products/{product_id}/prices` (offers, verified
  effective price, ranking reason, data freshness, adjustment provenance).
- `deal.py` — an intentionally empty placeholder schema; there is no `Deal` entity yet (see
  `ROADMAP.md` Phase 4/7).

These are deliberately kept separate from `app/db/models/` so the API contract never depends on
ORM internals (lazy-loaded relationships, mixins, column types) and can evolve independently of
the database schema.
