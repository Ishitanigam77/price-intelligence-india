# tests/unit/

Unit tests for domain logic and other pure/isolated components. Added alongside the real logic
they cover, starting in **Phase 1**.

- `test_domain_validation.py` covers `app/domain/validation.py`: slug/currency/country-code
  validation and product variant attribute normalization/`variant_key` derivation.
- `test_config.py` (FastAPI backend application foundation) covers `app.core.config.Settings`:
  defaults, `log_level` validation, and `cors_allowed_origins_list` parsing.
- `observability/` — JSON logging, correlation IDs, metrics sink.
- `matching/` — product identity matching engine: identifier/attribute/title/embedding stages,
  classification, evaluation precision/recall, and core-domain isolation.
- `pricing/` — price comparison engine (verified effective price, ranking, freshness) and
  Phase 7 historical intelligence (window averages, extrema, percentile, volatility,
  price-drop, trend, insufficient-history, provenance, isolation).
- `sales/` — Phase 9 sale-event intelligence (lifecycle, applicability, historical sale
  prices, calculated detection from concurrent drops, isolation).
- `ml/` — Phase 10 sale-price prediction (feature cutoff, leakage, chronological splits,
  INSUFFICIENT_DATA, XGBoost training, evaluation, inference schema, versioning).
- `recommendation/` — Phase 11 BUY / WAIT / WATCH engine (all four outcomes, missing/stale
  data, prediction fallback, upcoming events, determinism, no fabricated values, isolation).
- `retailer_adapters/` — adapter contract, registry, config, timeout/retry, rate limits,
  mock retailers, normalization, extensibility, and core-domain isolation.

No database or web framework is involved — these run anywhere Python runs.
