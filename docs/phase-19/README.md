# Phase 19 — Sale timing, price intelligence, and all-retailer comparison

Additive layer on Phase 0–18. No second comparison, matching, sale-event, ML, or
recommendation engine.

## Complete retailer comparison

`PriceComparisonEngine` ranks **every** persisted offer for the **exact** product variant.
The API `GET /api/v1/products/{id}/prices` returns the full `offers` list. The Product Details
page renders `offers.map(...)` with no `slice(0, 3)` (or equivalent) cap.

- 2 matching retailers → 2 offers
- 6 matching retailers → 6 offers
- 10 matching retailers → 10 offers

Offer count follows the data, not a hardcoded UI limit.

## Retailer vs seller

A **retailer** is a store identity (Demo Retailer A). A **seller/listing** is one offer on
that store. Two sellers on Amazon-style marketplaces are still **one retailer** and **two
offers**. Search cards report distinct retailer count; product details report both counts.

## Exact variant matching

Different variants stay separate (128GB is not merged with 256GB). Matching rules are not
weakened to inflate retailer count.

## Monthly intelligence vs historical chart

The 7/30/90/180-day chart is unchanged. Monthly statistics are a separate CALCULATED view.
If qualifying monthly observations exist but evidence is too thin to name a best month, the
UI still shows the month cards and labels **BEST BUYING MONTH — INSUFFICIENT HISTORY**.

## Sale timing

Reuses persisted `SaleEvent` rows and stored observations.

- Mapping: fixed-calendar, festival-relative, recurring, retailer-specific
- Evidence: CONFIRMED only for a persisted permitted/curated **future** event
- Classification: MAJOR / ORDINARY / UNKNOWN from duration, recurrence, and discount evidence
  (campaign names are not hardcoded as MAJOR)

## Expected sale price hierarchy

1. Usable Phase 10 PREDICTED price
2. Else CALCULATED historical sale-period median for matching variant + sale family + retailer
3. Else UNKNOWN / INSUFFICIENT_HISTORY

Expected savings require both a current effective price and a valid expected future price.
Negative savings are rejected. Sources stay labeled OBSERVED / CALCULATED / PREDICTED.

## Expected best retailer during a future sale

Independent of current cheapest retailer. Insufficient evidence → UNKNOWN. The current winner
is never copied forward.

## Phase 10 and Phase 11

Phase 10 XGBoost is reused. Missing artifacts → PREDICTED — NOT AVAILABLE / INSUFFICIENT_DATA.
No fabricated model or prediction.

Phase 11 remains the **primary** decision: BUY_NOW / WAIT / WATCH / INSUFFICIENT_DATA.
Urgency is optional and additive. A future sale without reliable priced savings does not
override a strongly favourable current price.

## Supported retailer adapters in this repository

| Adapter | How it is enabled | Live data in default local dev? |
|---|---|---|
| Mock retailers A/B/C | Default `RETAILER_ADAPTER_KINDS=mock` | No — fixture adapter data |
| Amazon.in Creators API | `RETAILER_ADAPTER_KINDS=integration` + credentials | Not unless credentials are supplied |
| Flipkart Affiliate API | same | Not unless credentials are supplied |

Ubuy, Myntra, Croma, Reliance Digital, and similar stores are **not** implemented. Do not
treat Demo Retailer A–F seed rows as those stores.

See `backend/app/retailer_adapters/INTEGRATIONS.md`.

## Configuration and credentials

Retailer credentials and API keys come from environment / Azure Key Vault only. Never commit
secrets. `.env.example` documents placeholders.

## Data honesty labels

| Label | Meaning |
|---|---|
| LIVE RETAILER DATA | Returned by a permitted adapter with real credentials |
| DEVELOPMENT FIXTURE DATA | Invented local seed / mock adapter rows, clearly labelled |
| OBSERVED | Stored `PriceSnapshot` / listing facts |
| CALCULATED | Derived from stored observations (monthly stats, effective price, savings) |
| PREDICTED | Phase 10 model output |
| UNKNOWN / INSUFFICIENT_DATA / INSUFFICIENT_HISTORY / NOT_AVAILABLE | Honest empty states |

## Development seed

`python -m scripts.seed_dev_data` (from `backend/`, `DATABASE_URL` = local Postgres) inserts
**DEVELOPMENT / TEST FIXTURE** rows:

- Product: `DEVELOPMENT FIXTURE: Demo Phone Z`
- Six distinct Demo Retailer identities on the **same** 128GB variant
- A second seller on Demo Retailer E (seven offers, six retailers)
- Separate 256GB variant (not merged)
- Multi-month / multi-year snapshots, ordinary + major sale families

Search for `Demo Phone Z`. These prices are not live retailer observations.

## APIs (preserved, additive fields only)

- `GET /api/v1/products/{id}/prices`
- `GET /api/v1/products/{id}/history` (includes `monthly`)
- `GET /api/v1/products/{id}/sale-intelligence`
- `GET /api/v1/products/{id}/sale-price-prediction`
- `GET /api/v1/products/{id}/recommendation` and `?urgency=urgent|patient`
- `GET /api/v1/sale-events/calendar`

Search also additively includes persisted catalogue products whose name matches `q`.

## Screenshots

Browser and API captures from the running local app live in `docs/phase-19/screenshots/`.
