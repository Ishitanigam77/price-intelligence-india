# app/services/

Thin service-layer boundaries, introduced only where they are genuinely required — most
catalogue API routes call a single Phase 1 repository directly via `app/api/deps.py` and need
no additional layer.

**Status**: FastAPI backend application foundation + Phase 4 product discovery + Phase 6
price comparison + Phase 7 historical price intelligence + Phase 9 sale-event intelligence.

- `price_service.py` — composes `RetailerProductRepository` + `PriceSnapshotRepository` so
  "get the price for a retailer listing" can distinguish "the listing doesn't exist" (404) from
  "the listing exists but has no observations yet" (an empty/absent result). No price
  computation, comparison, or prediction logic lives here.
- `product_discovery_service.py` — retailer-agnostic on-demand search: `RetailerFleet` over the
  `RetailerRegistry`, adapter `normalize_product`, persist via Phase 1 repositories, return
  standardized results. Timeouts/retries stay in the adapter executor. No semantic matching.
- `price_comparison_service.py` — loads matched listings/snapshots/adjustments for a product
  and asks `app.pricing.PriceComparisonEngine` to rank verified offers per variant.
- `price_history_service.py` — loads stored observations for a product and asks
  `app.pricing.PriceHistoryEngine` to compute per-variant historical intelligence
  (averages, extrema, percentile, volatility, drop, trend). Never fabricates missing history.
- `sale_event_service.py` — loads persisted `SaleEvent` rows and stored observations, then asks
  `app.sales.SaleEventEngine` for lifecycle status and historical sale-price analysis.
  Does not predict future sale prices.
- `sale_price_prediction_service.py` — loads the same stored observations and events, then asks
  the Phase 10 `ml` inference layer for a labeled predicted effective sale price (or
  `INSUFFICIENT_DATA`). Does not implement recommendations.
