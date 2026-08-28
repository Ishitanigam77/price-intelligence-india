# app/sales/

Sale-event intelligence: detects and tracks sale events and retains historical sale-price data
per product/variant for later ML features and recommendation context.

**Status**: implemented in **Phase 9 — Sale-Event Intelligence**.

This package is independent of FastAPI and of specific retailer adapters. It never predicts
prices (Phase 10+ / ML) and never fabricates real-world sale campaigns. Event records must
come from:

- manual curation (`source=manual_curation`)
- a legitimate permitted source already in hand (`official_api` / `affiliate_feed` /
  `product_feed` / `other_permitted`, with `source_ref`)
- calculated inference over stored price observations (`observed_price_inference`)

Test and development data must be clearly labeled as fictional fixtures.

- `enums.py` — insufficient-history codes owned by this package
- `config.py` — `SALES_*` detection/history thresholds
- `models.py` — retailer-agnostic records the engines consume and produce
- `lifecycle.py` — BEFORE / DURING / AFTER from `start_date` / `end_date`
- `applicability.py` — which events apply to a product/observation
- `history.py` — historical sale-price analysis from stored observations
- `detection.py` — inferred sale windows from concurrent observed price drops
- `engine.py` — facade composing lifecycle + history

Persistence lives in `app/db/models/sale_event.py` and `app/repositories/sale_event_repository.py`.
HTTP routes live in `app/api/v1/sale_events.py` and `GET /products/{id}/sale-history`.
