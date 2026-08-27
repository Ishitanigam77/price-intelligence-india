# app/pricing/

Price comparison engine: for each matched product variant, compares available retailer
offers and selects the best *verified* price using deterministic rules.

**Status**: implemented in **Phase 6 — Price Comparison Engine** and **Phase 7 —
Historical Price Intelligence**.

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
- `config.py` — `PRICING_FRESH_WITHIN_HOURS` / `PRICING_STALE_AFTER_HOURS`, plus Phase 7
  historical thresholds (`PRICING_TREND_STABLE_PERCENT`, minimum observation counts).
- `history.py` / `history_models.py` — Phase 7 historical price intelligence. Window
  averages (7/30/90/180-day), historical min/max, current-price percentile, volatility,
  percentage change, deterministic price-drop detection, and a non-ML historical trend.
  Calculations use only stored verified observations. Insufficient history is explicit;
  values are never fabricated. Predicted values are not produced.

Observed, calculated, and estimated values stay distinct (`price_kind` is
`verified_effective` or `displayed_only`; any unverified promotional figure is labeled
`estimated_unverified` and stored separately). Historical aggregates are labeled
`CALCULATED` and consume `OBSERVED` snapshots. Predicted values are out of scope (Phase 8).

Sale-event intelligence, watchlists/alerts, recommendation, and ML are **not** implemented
here.
