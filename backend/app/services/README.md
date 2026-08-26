# app/services/

Thin service-layer boundaries, introduced only where they are genuinely required — most
catalogue API routes call a single Phase 1 repository directly via `app/api/deps.py` and need
no additional layer.

**Status**: FastAPI backend application foundation + Phase 4 product discovery.

- `price_service.py` — composes `RetailerProductRepository` + `PriceSnapshotRepository` so
  "get the price for a retailer listing" can distinguish "the listing doesn't exist" (404) from
  "the listing exists but has no observations yet" (an empty/absent result). No price
  computation, comparison, or prediction logic lives here.
- `product_discovery_service.py` — retailer-agnostic on-demand search: `RetailerFleet` over the
  `RetailerRegistry`, adapter `normalize_product`, persist via Phase 1 repositories, return
  standardized results. Timeouts/retries stay in the adapter executor. No semantic matching.
