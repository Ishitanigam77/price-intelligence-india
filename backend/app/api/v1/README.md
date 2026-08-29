# app/api/v1/

The versioned `/api/v1/` API surface, mounted by `app.main.create_app` under
`Settings.api_v1_prefix` (default `/api/v1`). `__init__.py` aggregates every route module's
router into a single `api_router`; adding a new versioned resource means adding a module here
and including its router there — nothing else needs to change.

**Status**: FastAPI backend application foundation.

- `health.py` — `GET /api/v1/health` (liveness) and `GET /api/v1/health/ready` (readiness,
  reporting PostgreSQL and Redis availability independently; HTTP 503 if either is down).
- `products.py` — catalogue routes over `Product`/`ProductVariant` (list/get, filter by
  category/brand, list variants for a product) plus `GET /products/search` (Phase 4 product
  discovery via `ProductDiscoveryService`) and `GET /products/{product_id}/prices` (Phase 6
  price comparison via `PriceComparisonService`) and `GET /products/{product_id}/history`
  (Phase 7 historical intelligence via `PriceHistoryService`) and
  `GET /products/{product_id}/sale-history` (Phase 9 sale-event history via `SaleEventService`)
  and `GET /products/{product_id}/sale-price-prediction` (Phase 10 labeled prediction or
  `INSUFFICIENT_DATA` via `SalePricePredictionService`) and
  `GET /products/{product_id}/recommendation` (Phase 11 BUY_NOW / WAIT / WATCH /
  INSUFFICIENT_DATA via `RecommendationService`).
- `retailers.py` — read-only routes over `Retailer`/`Seller` (list/get, list sellers for a
  retailer).
- `prices.py` — read-only routes over `PriceSnapshot` via `app.services.price_service`
  (latest observation, history).
- `deals.py` — foundation-only placeholder: always returns an empty page. Deal detection
  depends on price-drop detection (Phase 4) and sale-event intelligence (Phase 7), neither of
  which exist yet.
- `sale_events.py` — Phase 9 sale-event intelligence: `GET /sale-events`,
  `GET /sale-events/upcoming`, and `GET /sale-events/{event_id}`.

No retailer scraping or product matching lives here. Catalogue routes are thin typed wrappers over Phase 1 repositories
(`prices.py` uses a small service composing two repositories). `GET /products/search` is a
thin typed wrapper over `ProductDiscoveryService`, which talks only to the retailer adapter
abstraction. `GET /products/{id}/prices` is a thin typed wrapper over
`PriceComparisonService`, which ranks persisted offers with the Phase 6 comparison engine.
`GET /products/{id}/history` is a thin typed wrapper over `PriceHistoryService`, which
computes historical aggregates from stored verified observations.
`GET /products/{id}/sale-history` and `/sale-events*` are thin typed wrappers over
`SaleEventService`. `GET /products/{id}/sale-price-prediction` is a thin typed wrapper over
`SalePricePredictionService` (Phase 10). `GET /products/{id}/recommendation` is a thin typed
wrapper over `RecommendationService` (Phase 11). The route does not train models or call an
LLM.
