# ml/

Sale-price prediction (Phase 10): feature engineering, chronological splitting, XGBoost
training, evaluation, versioned artifacts, and inference.

**Status**: implemented in **Phase 10 — Sale-Price Prediction**. The initial roadmap listed
this work under Phase 8; it is delivered after Phase 9 sale-event intelligence.

This package reuses stored `PriceSnapshot` observations (via `HistoricalObservationPoint` /
`SalePricePoint`) and `SaleEvent` records. It does **not** scrape retailers, invent
historical prices, or emit recommendations.

## Layout

- `features/` — leakage-safe feature engineering and the feature catalog (`features-v1`)
- `preprocessing/` — train-only categorical encoding; missing values stay `NaN`
- `training/` — labeled-example construction, chronological splits, XGBoost fit
- `evaluation/` — MAE / RMSE and validation-residual uncertainty
- `inference/` — load a model version and return a labeled prediction
- `models/` — artifact format, versioning, `artifacts/` (gitignored fitted files)
- `notebooks/` — exploratory analysis only; not production logic

## Target

Predict a listing's **effective sale price** (the median qualifying analysis price observed
during a sale window). Outputs are always `value_kind=PREDICTED` and `is_prediction=true`.
They are never observed prices, calculated aggregates, or guaranteed offers.

## Features (`features-v1`)

Numeric (missing → `None` / `NaN`, never zero-filled except where zero is a real count):

| Feature | Definition at prediction time T |
|---|---|
| `current_price` | Latest qualifying analysis price with `observed_at < T` and `created_at < T` |
| `avg_7d` / `avg_30d` / `avg_90d` | Phase 7 window averages on that cutoff set |
| `historical_low` / `historical_high` | Phase 7 extrema on that cutoff set |
| `price_volatility` | Phase 7 sample standard deviation on that cutoff set |
| `previous_sale_price` / `previous_sale_low` | Stats from sale windows that **ended** before T |
| `previous_sale_count` | Count of those completed windows with available stats (`0` is valid) |
| `mrp` | MRP on the current observation, if recorded |
| `days_until_sale` | Days until the next sale whose **schedule is knowable** at T |
| `month` / `day_of_week` / `day_of_year` / `is_weekend` | Calendar features of T |

Categorical (unknown at train time → missing, not a new code): `retailer_id`, `seller_id`,
`brand_id`, `category_id`, `sale_event_id`, `sale_event_type`.

## Leakage prevention

Mandatory rules, also stored on every `ModelMetadata.leakage_prevention`:

1. Features for timestamp T use only observations with `observed_at < T` **and**
   `created_at < T`. Same-instant and later rows are excluded.
2. Historical aggregates are computed on that cutoff set (Phase 7 engines, never a full
   future series).
3. Previous-sale features use only events with `end_date < T`.
4. Inferred sale events (`source=observed_price_inference`) are **not** treated as known
   upcoming/current events. They become historical facts only after they end.
5. Curated / permitted-source event schedules may be used for `days_until_sale` / event
   identity because those dates are treated as published. Their in-window prices still
   cannot enter features until observed and recorded before T.
6. The target effective sale price, and observations during the target window, are not
   input features.
7. Preprocessors are fit on the **training** split only.

## Time-based splitting

Primary evaluation is **not** a random train/test split.

Labeled examples are ordered by prediction timestamp (`as_of` = the target event's
`start_date`). Unique timestamps are cut into contiguous earlier → later ranges
(default 70% / 15% / 15% of timestamps). Every validation timestamp is at or after every
training timestamp; every test timestamp is at or after every validation timestamp.

## Training and insufficient data

`ml.training.train` builds examples from supplied observations and events, splits them,
fits XGBoost (`reg:squarederror`), and writes a versioned artifact.

If any of the following hold, it returns `INSUFFICIENT_DATA` and **writes no model**:

- No labeled examples (listing lacks pre-sale history or in-window sale observations)
- Training, validation, or test fold below `ML_MIN_*_ROWS`
- Empty feature matrix after preprocessing

Historical prices are never fabricated to force a fit.

Offline entrypoint (uses the database as-is):

```bash
cd backend && python -m scripts.train_sale_price_model
```

## Evaluation and uncertainty

Reported metrics are **MAE** and **RMSE** on the chronological **test** split (validation
metrics are stored alongside).

`lower_bound` / `upper_bound` are `predicted + P10/P90` of validation residuals
`(actual - predicted)`. `confidence` is

`clip(validation_coverage × feature_completeness / (1 + relative_RMSE), 0, 1)`

where `relative_RMSE = validation_RMSE / mean(validation targets)`. This is derived from
the validation split, not an arbitrary constant.

## Inference output

```
predicted_price, lower_bound, upper_bound, confidence,
model_version, training_data_size
```

plus `value_kind=PREDICTED`, `is_prediction=true`, and a disclaimer. HTTP:

`GET /api/v1/products/{product_id}/sale-price-prediction`

When no artifact exists or cutoff history is empty, `status=INSUFFICIENT_DATA` and the
price fields are null.

## Model versioning

Version string: `sale-price-xgb-features-v1-<UTC compact timestamp>`.

Metadata (minimum): model version, model type (`xgboost_regressor`), training timestamp,
training data size, feature version, MAE, RMSE, train/validation/test date ranges,
uncertainty method, leakage-prevention summary.

Artifacts live under `ml/models/artifacts/` (gitignored) with a `latest.json` pointer.

## Boundaries

- Must not import `app.api`, FastAPI, or a named retailer adapter package.
- `app.pricing` and `app.sales` must not import this package.
- Recommendation, notifications, Clerk, and infrastructure (Phase 11) are out of scope.
