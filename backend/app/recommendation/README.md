# app/recommendation/

Deterministic BUY_NOW / WAIT / WATCH / INSUFFICIENT_DATA engine. Combines Phase 7 historical
price intelligence, Phase 9 sale-event context, and optional Phase 10 XGBoost predictions
into an explainable decision.

**Status**: implemented in **Phase 11 — BUY / WAIT Recommendation Engine**, extended
additively in **Phase 19**.

This package is independent of FastAPI and of specific retailer adapters. It does **not**
train or invoke XGBoost, does **not** use an LLM / GPT / Claude / Gemini / Grok (or any
generative model) as a decision maker, and never fabricates prices, savings, events, or
confidence. Observed, calculated, and predicted values stay labeled separately.

## Layout

- `enums.py` — `Recommendation`, `BuyingWindow`, `Urgency`, `RuleId`, insufficient-data codes
- `config.py` — `RECOMMENDATION_*` thresholds including urgency horizons
- `models.py` — retailer-agnostic inputs/outputs
- `rules.py` — explicit documented rule evaluation, including optional Phase 19 windows
- `engine.py` — composes rules into one repeatable decision

HTTP lives in `GET /api/v1/products/{id}/recommendation` via `RecommendationService`.

When `urgency` is absent, Phase 11 BUY_NOW / WAIT / WATCH / INSUFFICIENT_DATA behaviour is
unchanged. Optional urgency may select `BUY_IN_ORDINARY_SALE` or `WAIT_FOR_MAJOR_SALE` as a
buying window; the primary `recommendation` field remains one of the four Phase 11 values.

## Decision rules (summary)

Gates (any one → `INSUFFICIENT_DATA`):

- no usable current effective / displayed price
- current observation is `stale` or `missing`
- qualifying historical observations below `RECOMMENDATION_MIN_OBSERVATIONS`

`BUY_NOW` when historical position is **strongly favorable** and no WAIT rule fires:

- percentile ≤ `buy_percentile_max` (default 25) and near historical low, or
- percentile ≤ `buy_strong_percentile_max` (default 15), or
- within `near_historical_low_strong_percent` (default 2%) of historical low, or
- favorable percentile and at/below both 30-day and 90-day averages
- usable Phase 10 prediction, when present, does not show material savings

`WAIT` when any of:

- current percentile ≥ `wait_percentile_min` (default 70) and not already at historical low
- current price is materially above 30/90-day averages
- usable predicted sale price is materially below current (expected saving is calculated)
- a credible upcoming sale event is in horizon and the current price is not a strong buy

`WATCH` when evidence is mixed, weak, or neutral (including conflicting BUY and WAIT
signals, low/moderate prediction confidence, or an upcoming event that is not credible).

When Phase 10 prediction is missing or below `min_prediction_confidence`, it is **unused**.
The engine falls back to historical and current-price signals and does not invent a
prediction. Recommendation `confidence` is an evidence-quality score; it is never a copy of
Phase 10 prediction confidence. `expected_saving` is set only when a usable predicted price
is below current; otherwise it is `null`.
