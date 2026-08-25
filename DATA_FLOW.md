# DATA_FLOW.md — PriceRadar India

> Describes how data is intended to flow through the system end to end. This is a design
> reference for future phases — no part of this pipeline is implemented in Phase 0.

## 1. High-Level Flow

```
[Legitimate Source]           [Backend / Workers]                         [Storage]        [Serving]
official API /       ┌───────────────────────────────────────────┐
affiliate feed /  →  │ Retailer Adapter (per retailer)             │
product feed         │   - discovery / listing fetch               │
                      │   - maps raw → common raw listing shape     │
                      └───────────────────┬───────────────────────┘
                                           ▼
                      ┌───────────────────────────────────────────┐
                      │ Collector (orchestrates adapters, handles   │
                      │ scheduling, retries, health reporting)       │
                      └───────────────────┬───────────────────────┘
                                           ▼
                      ┌───────────────────────────────────────────┐
                      │ Normalization                                │
                      │   - cleans text, units, currency              │
                      │   - extracts brand/model/variant attributes   │
                      └───────────────────┬───────────────────────┘
                                           ▼
                      ┌───────────────────────────────────────────┐
                      │ Matching                                     │
                      │   - resolves listing → existing Product      │
                      │     Variant, or flags as new/unmatched         │
                      │   - identifiers → text → embeddings, in that   │
                      │     order of preference                        │
                      └───────────────────┬───────────────────────┘
                                           ▼
                      ┌───────────────────────────────────────────┐        ┌────────────┐
                      │ Price Intelligence                           │  →   │ PostgreSQL │
                      │   - stores immutable Price Observations       │      │            │
                      │   - computes effective price when verifiable  │      │ Products   │
                      │   - detects genuine price drops                │      │ Variants   │
                      └───────────────────┬───────────────────────┘      │ Listings   │
                                           ▼                              │ Sellers    │
                      ┌───────────────────────────────────────────┐      │ Observations│
                      │ Sale-Event Intelligence                      │      │ Watchlists │
                      │   - detects/tracks sale events                 │      │ Alerts     │
                      └───────────────────┬───────────────────────┘      └─────┬──────┘
                                           ▼                                    │
                      ┌───────────────────────────────────────────┐            │
                      │ ML Inference (offline-trained, served async) │            │
                      │   - predicts likely sale price or             │            │
                      │     INSUFFICIENT_DATA                          │            │
                      └───────────────────┬───────────────────────┘            │
                                           ▼                                    │
                      ┌───────────────────────────────────────────┐            │
                      │ Recommendation Engine                        │            │
                      │   - BUY_NOW / WAIT / WATCH + explanation      │            │
                      └───────────────────┬───────────────────────┘            │
                                           ▼                                    ▼
                      ┌───────────────────────────────────────────┐   ┌─────────────────┐
                      │ Notifications                                │   │ FastAPI Backend  │
                      │   - price alert dispatch                       │   │ (read APIs)       │
                      └───────────────────────────────────────────┘   └────────┬────────┘
                                                                                 ▼
                                                                        ┌─────────────────┐
                                                                        │ Next.js Frontend  │
                                                                        │ search / compare /│
                                                                        │ charts / watchlist│
                                                                        └─────────────────┘
```

## 2. Stage-by-Stage Notes

### 2.1 Acquisition (Retailer Adapters + Collectors)

- Triggered on a schedule (Celery beat) or on-demand (e.g. user searches for a product not yet
  tracked).
- Each adapter only talks to its retailer's legitimate source and only returns data it actually
  received — never inferred or fabricated data.
- Collectors record health/success metrics per retailer for the retailer health feature.

### 2.2 Normalization

- Converts retailer-native fields (which vary wildly in naming, units, and structure) into one
  common "raw normalized listing" shape.
- No product-matching decisions happen here — this stage only cleans and standardizes.

### 2.3 Matching

- Attempts to resolve a normalized listing to an existing Product Variant using, in order of
  preference: GTIN/EAN/UPC → manufacturer part number/model number → brand + variant attributes
  → normalized text similarity → semantic embeddings (Sentence Transformers).
- Listings that cannot be confidently matched are held as "unmatched" for review rather than
  force-merged into an incorrect variant.
- Different variants (e.g. different storage/color) are never merged, even under time pressure
  to "just get a match."

### 2.4 Price Intelligence

- Every fetch produces an immutable Price Observation (see `RETAILER_ARCHITECTURE.md` §6 for
  its required fields).
- Effective price is calculated only when its inputs (coupon, payment discount, cashback,
  fees) are actually known/verified for that observation — otherwise it is left unset, not
  guessed.
- Historical series (7/30/90-day averages, min/max, volatility) are derived from stored
  observations, recomputed as new observations arrive.
- Price-drop detection compares new observations against historical baselines to distinguish a
  genuine drop from noise (e.g. a single anomalous reading).

### 2.5 Sale-Event Intelligence

- Groups observed price movements into named or inferred sale events, and retains historical
  sale price data per product/category for use as ML features.

### 2.6 ML Inference

- Consumes engineered features (see `TECH_STACK.md` / `ROADMAP.md` Phase 8) to predict a likely
  future sale price.
- Explicitly returns `INSUFFICIENT_DATA` rather than a low-confidence guess when history is
  inadequate.
- Predictions are always stored/displayed as predictions, never conflated with observed data.

### 2.7 Recommendation Engine

- Combines current price intelligence, sale-event context, and ML predictions into a
  BUY_NOW / WAIT / WATCH recommendation.
- Always produces a human-readable explanation referencing the specific facts that drove the
  recommendation (e.g. "current price is within 2% of the 90-day low" or "a sale event
  historically drops this category by X% and is predicted in N days").

### 2.8 Notifications

- Watchlist and price-alert rules are evaluated against new Price Observations and
  recommendations; matching rules trigger notification dispatch.

### 2.9 Serving (API + Frontend)

- FastAPI exposes read APIs for search, comparison, historical charts, retailer health, and
  recommendations, plus write APIs for watchlists/alerts (authenticated via Clerk).
- The Next.js frontend renders search, product comparison, historical price charts, retailer
  health/freshness indicators, and recommendation explanations.

## 3. Data Provenance Guarantee

At every stage, data can be traced back to: which retailer, which source type, which URL/feed
reference, and when it was observed. No stage in this pipeline introduces a value that isn't
either (a) directly observed from a legitimate source, (b) deterministically calculated from
verified observed values, or (c) an explicitly labeled prediction.
