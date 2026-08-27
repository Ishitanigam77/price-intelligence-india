# app/pricing/

Price comparison engine: for each matched product variant, compares available retailer
offers and selects the best *verified* price using deterministic rules.

**Status**: implemented in **Phase 6 — Price Comparison Engine**.

- `engine.py` — `PriceComparisonEngine` ranks offers per variant. Independent of FastAPI and
  of specific retailer adapter packages.
- `effective.py` — verified effective-price calculation. A coupon, cashback, payment discount,
  or other promotion reduces `effective_price` only when its eligibility is `verified_eligible`
  for that offer. Missing fees are never assumed to be zero.
- `ranking.py` — deterministic ranking: (1) lowest verified effective price, (2) lowest
  displayed price, (3) availability, (4) seller quality where available, (5) delivery
  information. Every selection carries an explainable `ranking_reason`. Unavailable offers
  cannot win the verified-price ranking. Unverified promotional prices are never used as the
  lowest verified price.
- `freshness.py` — data freshness from actual observation timestamps only. Never fabricates
  timestamps. Distinguishes `fresh` / `aging` / `stale` / `missing`.
- `models.py` — retailer-agnostic `OfferInput` / `ComparedOffer` / `ProductComparison`.
- `config.py` — `PRICING_FRESH_WITHIN_HOURS` / `PRICING_STALE_AFTER_HOURS`.

Observed, calculated, and estimated values stay distinct (`price_kind` is
`verified_effective` or `displayed_only`; any unverified promotional figure is labeled
`estimated_unverified` and stored separately). Predicted values are out of scope (Phase 8).

Sale-event intelligence, watchlists/alerts, recommendation, and ML are **not** implemented
here.
